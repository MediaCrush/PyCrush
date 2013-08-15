import requests
import re

re_path_template = re.compile('\<\w+\>')

class PyCrushError(Exception): pass

def bind(**cfg):
    class APIMethod(object):
        endpoint = cfg['endpoint'] # It's okay to blow up if the endpoint is not provided.
        method = cfg.get('method', 'GET')
        required_parameters = cfg.get('parameters', []) 
        _args = None

        def __init__(self, base, params):
            self._url = base + self.endpoint

            for v in re_path_template.findall(self._url):
                name = v.strip('<>')
                try:
                    value = params[name]
                    if isinstance(value, list):
                        value = ','.join(value)
                except KeyError:
                    raise PyCrushError("Variable %r has no value." % name)
                
                del params[name] # If we get here it means it's not a POST param and is safe to delete.
                self._url = self._url.replace(v, value)
            
            for param in self.required_parameters:
                if param not in params:
                    raise PyCrushError("Required parameter %r is not present." % param)
                
                self._args[param] = params[param]
             
        def run(self):
            if self._args:
                rq = requests.request(self.method, self._url, **self._args)
            else:
                rq = requests.request(self.method, self._url)
            return rq.json(), rq.status_code

    def _call(api, **params): # _call is called as an instance method; i.e, `api` is `self`.
        return APIMethod(api.base, params).run()

    return _call

class API(object):
    def __init__(self, base='https://mediacru.sh/api'):
        self.base = base

    single = bind(
        endpoint='/<hash>'
    )
    info = bind(
        endpoint='/info?list=<list>'
    )
    exists = bind(
        endpoint='/<hash>/exists'
    )
    delete = bind(
        endpoint='/<hash>/delete',
        method='DELETE'
    )
    status = bind(
        endpoint='/<hash>/status'
    )

    upload_file = bind(
        endpoint='/upload/file',
        method='POST',
        parameters=['file']
    )

    upload_url = bind(
        endpoint='/upload/url',
        method='POST',
        parameters=['url']
    )

if __name__ == '__main__':
    api = API()

    print api.exists(hash='V_3ZkEzIUW9E')
    print api.info(list=['V_3ZkEzIUW9E', '6-5E-TOqYQAr'])
