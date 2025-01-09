import logging
from odoo.http import request, JsonRPCDispatcher, BadRequest
from .main import alternative_json_response

_logger = logging.getLogger(__name__)


class JsonRPCDispatcherInherit(JsonRPCDispatcher):

    def dispatch(self, endpoint, args):
        """
        `JSON-RPC 2 <http://www.jsonrpc.org/specification>`_ over HTTP.

        Our implementation differs from the specification on two points:

        1. The ``method`` member of the JSON-RPC request payload is
           ignored as the HTTP path is already used to route the request
           to the controller.
        2. We only support parameter structures by-name, i.e. the
           ``params`` member of the JSON-RPC request payload MUST be a
           JSON Object and not a JSON Array.

        In addition, it is possible to pass a context that replaces
        the session context via a special ``context`` argument that is
        removed prior to calling the endpoint.

        Successful request::

          --> {"jsonrpc": "2.0", "method": "call", "params": {"context": {}, "arg1": "val1" }, "id": null}

          <-- {"jsonrpc": "2.0", "result": { "res1": "val1" }, "id": null}

        Request producing a error::

          --> {"jsonrpc": "2.0", "method": "call", "params": {"context": {}, "arg1": "val1" }, "id": null}

          <-- {"jsonrpc": "2.0", "error": {"code": 1, "message": "End user error message.", "data": {"code": "codestring", "debug": "traceback" } }, "id": null}

        """
        try:
            self.jsonrequest = self.request.get_json_data()
        except ValueError as exc:
            raise BadRequest("Invalid JSON data") from exc

        self.request.params = dict(self.jsonrequest.get('params', {}), **args)
        ctx = self.request.params.pop('context', None)
        if ctx is not None and self.request.db:
            self.request.update_context(**ctx)

        if self.request.db:
            result = self.request.registry['ir.http']._dispatch(endpoint)
        else:
            result = endpoint(**self.request.params)

        if endpoint.routing.get('custom_response'):
            return alternative_json_response(self, result=result)
        return self._response(result)


JsonRPCDispatcher.dispatch = JsonRPCDispatcherInherit.dispatch
