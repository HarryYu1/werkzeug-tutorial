import os
import redis 
from werkzeug.urls import url_parse
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.utils import redirect
from jinja2 import Environment, FileSystemLoader

class Shortly(object):

    def __init__(self, config):
        self.redis = redis.Redis(config["redis_host"], config["redis_port"], decode_responses = True)

    #werkzeug packages things into response/request object for easy use
    def dispatch_request(self, request):
        return Response("Hello World!")
    
    #the actual app part that follows the structure
    def wsgi_app(self, environ, start_response):
        request = Request(environ)  #incoming request, takes data from the environ
        response = self.dispatch_request(request) #calls our own helper function
        return response(environ, start_response)

    #links our app to the call
    def __call__(self, environ, start_response):
        #put here supposedly to set up the middleware
        return self.wsgi_app(environ, start_response)

#sets up the app
def create_app(redis_host = 'localhost', redis_port = 6379, with_static = True):
    app = Shortly({
        "redis_host" : redis_host,
        "redis_port" : redis_port
    })
    #registers the shared data which is in the static folder I think
    if with_static:
        app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {'/static' : os.path.join(os.path.dirname(__file__), 'static')})
    return app

#set up debugger and run
if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader = True)