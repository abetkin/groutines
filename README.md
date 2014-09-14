Patching: the white people method
=================================

With this I shall introduce **groutines** framework.
It's aim is to see what runtime-controlled patching can bring us. In my opinion, that idea wasn't fully exploited yet.

Speaking of patching, it supports only patching callables, namely, you can add pre- or post-hooks or replace the callable entirely. It is done implicitly for you, all your code needs to do is to subscribe at runtime to the event of calling some method.

About the code you need to write: it is supposed to be structured into groutines (basically, [greenlets](http://greenlet.readthedocs.org)), an independent, discoverable (something like a test) piece of code. As opposed to tests, they are alive altogether (not run one by one) and can fire and listen to events.

how it appeared
----------------
The initial aim was to give tests the ability to "listen" to some method so that to be able to add checks on its parameters and the return value. As later the range where it could be possibly applied widened, I focused on implementing the core functionality, so there is no any integration with testing at all in the current version.

range of application
---------------------
Everywhere except production: testing, debugging, logging, writing code, etc. Also I believe that the worse is the code,
the more this framework is needed.

global scenario
-----------------
The framework is lazy: it does not run code itself, instead, it (temporary) patches external code's functions so that it's code would be run. This external scenario can be a script, a test, or a server responding on user request. It is not required to know anything about the framework.

groutine
----------
In current version it is just a [greenlet](http://greenlet.readthedocs.org), which is an execution context that can be given control by switching into it. But, unlike the function, two greenlets can switch data back and forth many times, and unlike the generator, any greenlet has a parent, etc. *Greenlets are executed in the same thread with the rest of the program, there is no event loop occupying a thread.*

Groutine is a relatively independent unit in the framework. In most cases they just respond to and fire the events (events carry data), and also can directly switch data with the parent. They serve the main goal of the framework: to be able to test (or debug, or log) logically unrelated stuff separately. Or conversely, to put logically correlated stuff together.

Examples
-------------
The framework isn't related in any kind to web, but since it's what majority is interested in.. the example application will be [this](https://github.com/tomchristie/rest-framework-tutorial)
(the official example of using [Django REST Framework](http://www.django-rest-framework.org/)). The global scenario will be this request:
    
    POST /snippets/ title=aaa code=bbb

The code below allows to add new snippet instance by not authorized user (the action normally forbidden). It  demonstrates the simplest use of the framework: just patching.
(To see how it was intrgrated with [django](https://www.djangoproject.com/), see ``middleware.GMiddleware``).

    @groutine()
    def start_view():
        view, request = FunctionCall(
                'rest_framework.views.APIView.dispatch').wait('ENTER')
        Event('DISPATCH').fire(view, request)

    @groutine(FunctionCall('rest_framework.views.APIView.check_permissions'), typ='ENTER')
    def check_permissions(view, request, **kw):
        return True


    @groutine(Event('DISPATCH'))
    def fill_user(view, request):
        _, snippet = FunctionCall((view, 'pre_save')).wait(typ='ENTER')
        snippet.owner = User.objects.get(username='vitalii')

``FunctionCall`` event is fired when corresponding callable gets called. This event carries positional and
keyword arguments the callable was called with. Two patches (``check_permissions``
and ``fill_user``) show two ways of referencing callables: by absolute import path and by object's attribute (it could be referenced by class atribute 
as well). 'ENTER' and 'EXIT' are two types of ``FunctionCall`` event: respective, before and after the underlying function call.

Another small example: when we get a "not ok" response like 400, we can't always tell from its message what happened.
Exception is better: it prints the stack of frames. Let's change one with the other: ``Response`` is a class, hence, a callable.
    
    @groutine(FunctionCall('rest_framework.response.Response',
                           argnames=('data', 'status')))
    def make_responses_raise_exc(data, status, *args, **kw):
        if status // 100 != 2:
            raise Exception(data)
    
*Note*: ``FunctionCall`` has positional and keyword arguments as a value it carries, those are what the underlying callable (here - ``Response`` class) was passed. But one can pass positional argument as keyword to a function. So, we can't know exact number of positional arguments event carries.
To solve this, you can pass ``argnames`` parameter: now even if some of ``argnames`` items will be passed as keyword, they will be made positional.
In Python 3 the solution wouldn't require passing additional parameter (``argnames``), since [Signature](https://docs.python.org/3/library/inspect.html#inspect.Signature) class
is smart enough to figure the actual function's signature out.

An example of groutine that represents an infinite loop:
    
    @groutine(FunctionCall('rest_framework.serializers.Field.field_from_native'),
              loop=True)
    def print_field_names(field, data, files, field_name, into, **kw):
        print field_name, '->', into.get(field_name, '----')

TO BE CONTINUED!
-----------------
As I said, only the core functionality is provided yet, and since possible extensions / applications of the framework are easier to write than to explain, await new code in the near future!

