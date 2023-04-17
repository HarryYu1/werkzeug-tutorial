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
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader = FileSystemLoader(template_path), autoescape = True)
        #routing: mapping and parsing the url to something we can use
        self.url_map = Map([
            Rule('/', endpoint= 'new_url'),
            Rule('/<short_id>', endpoint = 'follow_short_link'),
            Rule('/<short_id>+', endpoint = 'short_link_details')
        ])

    #werkzeug packages things into response/request object for easy use
    #binds the map to the environment (request has environ attribute)
    #python syntax thing - the f means that the thing in curly brackets is replaced by the value
    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            #this part grabs the attribute from the map and then calls the associated function?
            return getattr(self, f'on_{endpoint}')(request, **values)
        except HTTPException as e:
            return e
    
    #a helper function that checks if the scheme is http or https
    def is_valid_url(url):
        parts = url_parse(url)
        return parts.scheme in ('http', 'https')


    def on_new_url(self, request):
        error = None
        url = ''
        #if the method is post
        if request.method == 'POST':
            #grabs the url from the request
            url = request.form['url']
            #validates
            if not is_valid_url(url):
                error = 'Please enter valid url'
            else:
                short_id = self.insert_url(url)
                #redirects to short link details
                return redirect(f"/{short_id}+")
        return self.render_template('new_url.html', error=error, url=url)
    
    #checks to see if it exists by getting it, then if it doesn't stores it with an id that's a base36 encode version
    def insert_url(self, url):
        short_id = self.redis.get(f'reverse-url:{url}')
        if short_id is not None:
            return short_id
        url_num = self.redis.incr('last-url-id')
        short_id = base36_encode(url_num)
        self.redis.set(f'url-target:{short_id}', url)
        self.redis.set(f'reverse-url:{url}', short_id)
        return short_id
    
    #helper function to encode base 36
    def base36_encode(number):
        assert number >= 0, 'positive integer required'
        if number == 0:
            return '0'
        base36 = []
        while number != 0:
            number, i = divmod(number, 36)
            base36.append('0123456789abcdefghijklmnopqrstuvwxyz'[i])
        return ''.join(reversed(base36))

    #renders a template
    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype = 'text/html')
    
    #the actual app part that follows the structure
    def wsgi_app(self, environ, start_response):
        request = Request(environ)  #incoming request, takes data from the environ
        response = self.dispatch_request(request) #calls our own helper function

        #the call function of Response processes it as a WSGI application
        return response(environ, start_response)

    #links our app to the call
    def __call__(self, environ, start_response):
        #put here supposedly to set up the middleware
        return self.wsgi_app(environ, start_response)
    
    #basically if somebody goes to the short link
    #the map basically tells which short id
    def on_follow_short_link(self, request, short_id):
        link_target = self.redis.get(f'url_target:{short_id}')
        if link_target is None:
            raise NotFound()
        #increase click count
        self.redis.incr(f'click_count:{short_id}')
        return redirect(link_target)
    
    #the details which tells details about the link
    def on_short_link_details(self, request, short_id):
        link_target = self.redis.get(f'url-target:{short_id}')
        if link_target is None:
            raise NotFound()
        click_count = int(self.redis.get(f'click-count:{short_id}') or 0)
        return self.render_template('short_link_details.html',
            link_target=link_target,
            short_id=short_id,
            click_count=click_count
    )



#sets up the app
def create_app(redis_host = 'localhost', redis_port = 6379, with_static = True):
    app = Shortly({
        "redis_host" : redis_host,
        "redis_port" : redis_port
    })
    #registers the shared data which is in the static folder I think
    #so now we can use it
    if with_static:
        app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {'/static' : os.path.join(os.path.dirname(__file__), 'static')})
    return app

#set up debugger and run
if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader = True)