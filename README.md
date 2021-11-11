# Requirements Note

This project was a take-home code test. I don't want to just cut-and-paste
the requirements, but the ask was for a RESTful short-URI app. The user could
submit URLs and get back a short-form, be redirected through the short-form,
and get a list of sll existing short URLs including time since creation and
targets. Needed to include instructions to install, test, and run (this
document). Deployment was not required.

I hadn't used Flask before, but it was part of the requestor's tech stack.
It's a decent little web service framework, not too hard to pick up.

# Installation & Setup, Linux or macOS:

    $ git clone https://github.com/mgsouth/msouth-ur
    $ cd msouth-ur
    $ python3 -m venv venv
    $ . venv/bin/activate
    $ pip install click
    $ pip install Flask

Launch the service:

    $ export FLASK_ENV=development
    $ python ur.py

Clear out the saved short urls:

    $ rm redirs.*

# Examples

In a terminal session:

    $ export FLASK_ENV=development
    $ python ur.py

In a separate terminal session:

    $ curl -i -d '{"long_url": "http://whatever.com"}' 'http://127.0.0.1:5000/redirs/'

=>

    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 155
    Server: Werkzeug/2.0.1 Python/3.6.5
    Date: Fri, 16 Jul 2021 09:42:22 GMT
    
    {
      "reason": "",
      "redir": {
        "age": 0,
        "long_url": "http://whatever.com",
        "short_url": "http://127.0.0.1:5000/C"
      },
      "status": "OK"
    }

    $ curl -i -d '{"long_url": "https://en.wikipedia.org/wiki/URL_shortening"}' 'http://127.0.0.1:5000/redirs/'
    $ curl -i -d '{"long_url": "http://127.0.0.1:5000/redirs/"}' 'http://127.0.0.1:5000/redirs/'
    $ curl -i 'http://127.0.0.1:5000/redirs/'

=>

        HTTP/1.0 200 OK
        Content-Type: application/json
        Content-Length: 451
        Server: Werkzeug/2.0.1 Python/3.6.5
        Date: Fri, 16 Jul 2021 09:51:24 GMT
        
        {
          "reason": "",
          "redirs": [
            {
              "age": 390,
              "long_url": "http://whatever.com",
              "short_url": "http://127.0.0.1:5000/C"
            },
            {
              "age": 369,
              "long_url": "https://en.wikipedia.org/wiki/URL_shortening",
              "short_url": "http://127.0.0.1:5000/D"
            },
            {
              "age": 243,
              "long_url": "http://127.0.0.1:5000/redirs/",
              "short_url": "http://127.0.0.1:5000/E"
            }
          ],
          "status": "OK"
        }
        
-----

In the following, we need the -L so that curl will actually follow the redirect.

    $ curl -i -L http://127.0.0.1:5000/D
=>

        HTTP/1.0 302 FOUND
        Content-Type: text/html; charset=utf-8
        Content-Length: 294
        Location: https://en.wikipedia.org/wiki/URL_shortening
        Server: Werkzeug/2.0.1 Python/3.6.5
        Date: Fri, 16 Jul 2021 09:52:34 GMT
        
        HTTP/2 200
        date: Thu, 15 Jul 2021 20:15:58 GMT
        vary: Accept-Encoding,Cookie,Authorization
        server: ATS/8.0.8
        x-content-type-options: nosniff
        p3p: CP="See https://en.wikipedia.org/wiki/Special:CentralAutoLogin/P3P for more info."
        content-language: en
        last-modified: Mon, 12 Jul 2021 21:28:15 GMT
        content-type: text/html; charset=UTF-8
        age: 48996
        ...
        
## Shortened POST:

So meta... but it's a handy site which accepts POSTs

    $ curl -i -d '{"long_url": "http://127.0.0.1:5000/redirs/"}' 'http://127.0.0.1:5000/redirs/'

=>

    "short_url": "http://127.0.0.1:5000/F"

In the next command, note there's no trailing slash after the F.

Without the --post302 curl with do a GET on the redirect rather than a POST.

    $ curl -i -L --post302 -d '{"long_url": "https://news.ycombinator.com"}' 'http://127.0.0.1:5000/F'

=>

    HTTP/1.0 302 FOUND
    Content-Type: text/html; charset=utf-8
    Content-Length: 264
    Location: http://127.0.0.1:5000/redirs/
    Server: Werkzeug/2.0.1 Python/3.6.5
    Date: Fri, 16 Jul 2021 09:58:07 GMT
    
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 164
    Server: Werkzeug/2.0.1 Python/3.6.5
    Date: Fri, 16 Jul 2021 09:58:07 GMT
    
    {
      "reason": "",
      "redir": {
        "age": 0,
        "long_url": "https://news.ycombinator.com",
        "short_url": "http://127.0.0.1:5000/G"
      },
      "status": "OK"
    }
        
# REST API

    * Insert a long -> short redirection.

        POST <host>/redirs/
        { "long_url": <target> }

    =>

        { "status": "OK",
          "reason": "",
          "redir": {
              "short_url":  <URL>,
              "long_url":   <URL>,
              "age":        <age of entry, in seconds, relative to current time>,
          }
        }

    -or-

        { "status": "ERROR",
          "reason": <note describing error>,
          "redir":  null,
        }


    * Get a list of all redirections.

        GET <host>/redirs/

    =>

        { "status": "OK"
          "reason": "",
          "redirs": [
              {
                  "short_url":  <URL>,
                  "long_url":   <URL>,
                  "age":        <age of entry, in seconds, relative to current time>,
              }
              ...
          ]
        }
