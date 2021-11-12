import sqlite3
import time
from flask import Flask, g, json, jsonify, make_response, redirect, request, url_for

# URL-shortening service.
# Provides RESTful API for creating and querying shortened URLs. Redirects
# short URLs to long targets.
#
# ***TOY APP, SECURITY NIGHTMARE***
# No users, no authentication, no checks for malicious long URLs. Unexpected
# SQL errors abort the program.

# Base path for redirection REST API. I.E., requests will be to
# HTTP://<host>/<APIROOT>/
APIROOT = 'redirs'

DATABASE='redirs.db'

app = Flask(__name__)


# DAO-ish

# Internal and external views of REDIRS differ. Internal has a short-URL *path*,
# external has a full URL. External synthesizes an 'age' column, internal has
# a more-sensible timestamp. IRL you probably wouldn't want age, but that's the
# literal ask in the problem and it makes for an interesting twist.

# Flask's worldview begins and ends with an "application context", which only
# exists while a HTTP request is being processed. It does not support variables
# with indefinite lifetimes, so we can't have a globally-scoped cache DB
# instances without stepping outside of Flask.
#
# Even variables with an application-context lifetime require that we register
# them as an attribute cached in the context. This function returns the
# context's database connection, or creates a new one if this is the first time
# within this HTTP request.
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

# appcontext teardown happens when we've finished responding to the HTTP req.
@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize the database by setting up table and such. Idempotent--has no
    effect if the database has already been initialized."""
    
    # We don't have any globals, so we must use the database to keep track of
    # the next short-URL to use. A fairly efficient way to do this in sqlite
    # is to (abuse) the user_version pragma.
    
    # We use sqlite's user_version pragma as the next short-url ID, and as a
    # sentinel that the schema has already been configured.
    with app.app_context():
        with get_db() as db:
            cur = db.execute('PRAGMA user_version')
            v = cur.fetchone()
            if v[0] == 0:
                db.execute('CREATE TABLE redirs (short_path text primary key, long_url text, create_tstamp integer)')
                db.execute('PRAGMA user_version=1')

def short_path_to_url(sp):
    """Given a short-URI endpoint (such as 'SHORTY'), return the full URL that
    should be used (such as http://myshortserver.com:5000/SHORTY')."""
    sn_host, sn_port = None, None
    sn = app.config.get('SERVER_NAME')
    if sn is not None:
        sn_host, _, sn_port = app.config.get('SERVER_NAME').partition(':')
    return f'http://{sn_host or "127.0.0.1"}:{sn_port or 5000}/{sp}'

def redir_to_ext(redir):
    """Return a dict with the external view of a short-cut; short_url contains
    the full URL, age is synthesized."""
    if redir is None: return None
    return {
        "short_url": short_path_to_url(redir['short_path']),
        "long_url": redir['long_url'],
        # It is possible for clock corrections to make time run backwards a bit,
        # so pin age to >= 0.
        "age": max(int(time.time()) - redir['create_tstamp'], 0),
    }

def find_all_redirs():
    """Return a dict with all the shortcuts in the database."""
    cur = get_db().execute('SELECT short_path, long_url, create_tstamp FROM redirs')
    # IRL: Paging
    rslt = cur.fetchall()
    cur.close()
    return [{"short_path": r[0], "long_url": r[1], "create_tstamp": r[2]} for r in rslt]

def find_redir_short(short_path):
    """Given a short URI ('SHORTY', not the full URL or endpoint), find the
    already-existing shortcut and return it as an internal-view dict (short
    path not URL, timestamp not relative time)."""
    if short_path is None: return None
    cur = get_db().execute('SELECT short_path, long_url, create_tstamp FROM redirs WHERE short_path = ?',
        short_path)
    rslt = cur.fetchall()
    cur.close()
    if len(rslt) > 0:
        return {"short_path": rslt[0][0], "long_url": rslt[0][1], "create_tstamp": rslt[0][2]}
    else:
        return None

def insert_redir(long_url):
    """Given a long URL, create a new shortcut, insert it into the database,
    and return an internal-view dict (short path not URL, timestamp not
    relative time)."""
    # Note: avoid returning the word "redirs", since that is reserved by the
    # REST API.
    db = get_db()
    redir = {
        "short_path": None,
        "long_url": long_url,
        "create_tstamp": int(time.time())
    }
    # Keep creating short URLs until we get one that is valid and unused. In
    # real life we'd want to create something deterministically unique across
    # server instances and threads.
    while True:
        # Get the next short-url ID
        cur = db.execute('PRAGMA user_version')
        v = cur.fetchone()[0] + 1
        cur.close()
        db.execute(f'PRAGMA user_version={v}')

        # Look, all I want to do is format an integer as base64. Is that too
        # much to ask?
        b64 = ''
        alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        while True:
            b64 = alpha[v % 64] + b64
            v = v // 64
            if v == 0: break
        if b64.upper() == APIROOT.upper(): continue
        redir['short_path'] = b64
        try:
            db.execute('INSERT INTO redirs (short_path, long_url, create_tstamp) VALUES (?, ?, ?)',
                (b64, redir['long_url'], redir['create_tstamp']))
        except sqlite3.IntegrityError:
            # Duplicate key
            continue
        else:
            db.commit()
            break
    return redir


# REST API

def sanitize_long(long_url):
    """Perform very minimal sanitizing of the long URL we got from the
    caller."""
    rslt = (long_url if long_url is not None else '').lstrip().rstrip()
    return rslt if rslt != '' else None

def rslt_redir(status, reason, redir):
    """Create a result dict object."""
    rslt = jsonify({
        "status": status,
        "reason": reason,
        "redir": redir_to_ext(redir),
    })
    print(f'rslt_redir={rslt}')
    return rslt

def rslt_redir_list(status, reason, redirs):
    """Create a result dict object which includes a list of redirections."""
    rslt = {
        "status": status,
        "reason": reason,
        "redirs": [],
    }
    if redirs is not None:
        rslt["redirs"] = [redir_to_ext(rd) for rd in redirs]
    return jsonify(rslt)

@app.route(f'/{APIROOT}/', methods=['POST'])
def post_redir():
    """Handle a REST POST to create a new shortcut."""
    req = request.get_json(force=True, silent=True)
    lu = sanitize_long(req.get('long_url')) if req is not None else None
    if lu is not None:
        return rslt_redir('OK', '', insert_redir(lu))
    else:
        return {
            "status": 'ERROR',
            "reason": 'Expected json data {"long_url": VALUE}',
            "redir": None,
        }

@app.route(f'/{APIROOT}/<path:short_path>', methods=['GET'])
def get_redir_short(short_path):
    """Handle a REST GET for a particular short path."""
    redir = select_redir_short(short_path)
    if redir is None:
        return rslt_redir('ERROR', 'No such short path', None)
    else:
        return rslt_redir('OK', '', redir)
    
@app.route(f'/{APIROOT}/', methods=['GET'])
def get_redirs():
    """Handle a REST GET for all shortcuts"""
    return rslt_redir_list('OK', '', find_all_redirs())


# Redirection service

@app.route('/<string:short_path>', methods=['GET', 'POST', 'PUT'])
def redir_short(short_path):
    """Handle a GET, POST, or PUT to a short URL (non-REST)."""
    redir = find_redir_short(short_path)
    if redir is None:
        return make_response(render_template('error.html'), 404)
    else:
        return redirect(redir['long_url'])


# Start

if __name__ == '__main__':
    init_db()
    app.run()
