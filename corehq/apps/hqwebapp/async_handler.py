import json
from django.http import HttpResponse, HttpRequest


class AsyncHandlerError(Exception):
    pass


class BaseAsyncHandler(object):
    """
    Handles serving async responses for an ajax post request, say in a form.
    Usage:
    1) specify an allowed action slug in allowed actions
    2) implement the property <allowed action slug>_response, which returns a dict.
    example:

    allowed_actions = [
        'create'
    ]
    then implement

    @property
    def create_response(self):
        return {}

    """
    slug = None
    allowed_actions = []

    def __init__(self, request):
        if not isinstance(request, HttpRequest):
            raise ValueError("request must be an HttpRequest.")
        self.request = request
        self.data = request.POST if request.method == 'POST' else request.GET
        self.action = self.data.get('action')

    def _fmt_error(self, error):
        return json.dumps({
            'success': False,
            'error': error.message,
        })

    def _fmt_success(self, data):
        return json.dumps({
            'success': True,
            'data': data,
        })

    def get_action_response(self):
        if self.action not in self.allowed_actions:
            raise AsyncHandlerError("Action '%s' is not allowed." % self.action)
        response = getattr(self, '%s_response' % self.action)
        return self._fmt_success(response)

    def get_response(self):
        try:
            response = self.get_action_response()
        except AsyncHandlerError as e:
            response = self._fmt_error(e)
        except TypeError as e:
            response = self._fmt_error(e)
        return HttpResponse(response, content_type='application/json')
