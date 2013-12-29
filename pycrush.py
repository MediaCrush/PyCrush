import requests
import re
import time

re_path_template = re.compile('\<\w+\>')

class PyCrushException(Exception): pass
class SpecificException(PyCrushException):
    def __init__(self, message, code):
        super(PyCrushException, self).__init__(self, message)
        self.code = code
        self.message = message

class UploadException(SpecificException): pass
class MediaException(SpecificException): pass
class ProcessingException(SpecificException): pass

def bind(**cfg):
    class APIMethod(object):
        endpoint = cfg['endpoint'] # It's okay to blow up if the endpoint is not provided.
        method = cfg.get('method', 'GET')
        required_parameters = cfg.get('parameters', []) 

        _args = dict() 
        _request_kwargs = dict()

        def __init__(self, base, params):
            self._url = base + "api" + self.endpoint

            for v in re_path_template.findall(self._url):
                name = v.strip('<>')
                try:
                    value = params[name]
                    if isinstance(value, list):
                        value = ','.join(value)
                except KeyError:
                    raise PyCrushException("Variable %r has no value." % name)
                
                del params[name] # If we get here it means it's not a POST param and is safe to delete.
                self._url = self._url.replace(v, value)
            
            for param in self.required_parameters:
                if param not in params:
                    raise PyCrushException("Required parameter %r is not present." % param)
       
                value = params[param] 
                if param == 'file':
                    self._request_kwargs['files'] = {param: value}
                else:
                    self._args[param] = value 
   
            self._request_kwargs['data'] = self._args 
             
        def run(self):
            rq = requests.request(self.method, self._url, **self._request_kwargs)
            return rq.json(), rq.status_code

    def _call(api, **params): # _call is called as an instance method; i.e, `api` is `self`.
        return APIMethod(api.base, params).run()

    return _call

class API(object):
    def __init__(self, base='https://mediacru.sh/'):
        if base[-1] != "/":
            base += "/"
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
        endpoint='/<hash>',
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

class LazyProperty(object):
    sources = {
        'compression': 'single',
        'files': 'single',
        'original': 'single', 
        'type': 'single',
        'status': 'status'
    }

    bad_statuses = {
        'processing': 'The file is being processed or is in the queue.',
        'error': 'The processing step finished early with an abnormal return code.',
        'timeout': 'The file took too long to process.'
    }

    def __init__(self, name):
        self.name = name

    def __get__(self, instance, owner):
        func = getattr(instance.api, self.sources.get(self.name, instance.api.single))
        
        result, code = func(hash=instance.hash)
        if code != 200:
            raise MediaException("The media cannot be found", code) 

        instance.populate(result)
        if self.name != 'status' and instance.status in self.bad_statuses:
            raise ProcessingException(self.bad_statuses[instance.status], instance.status)

        return result[self.name]

class Media(object):
    @classmethod
    def upload(cls, obj, base='https://mediacru.sh'):
        api = API(base)

        failure_codes = {
            400: 'The URL is invalid.',
            404: 'The requested file does not exist.',
            415: 'The file extension is not acceptable.',
            420: 'The rate limit was exceeded. Enhance your calm.'
        }

        success_codes = {
            200: 'The file was uploaded correctly.',
            409: 'The file was already uploaded.'
        }

        if isinstance(obj, file):
            result, code = api.upload_file(file=obj)
        elif isinstance(obj, str): # It's a string -> URL.
            result, code = api.upload_url(url=obj)
        
        if code in failure_codes:
            raise UploadException(failure_codes[code], code)
        if code not in success_codes:
            raise PyCrushException("MediaCrush returned an unknown code (%d)." % code)
   
        result.update({
            'message': success_codes[code],
            'code': code,
            'api': api
        })

        return cls(**result)

    @classmethod
    def get(cls, hash, base='https://mediacru.sh'):
        api = API(base)

        result, code = api.exists(hash=hash)

        if code != 200:
            raise MediaException("The media cannot be found.", code)

        params = {
            'hash': hash, 
            'api': api,
        }

        return cls(**params)


    compression = LazyProperty('compression')
    files = LazyProperty('files')
    original = LazyProperty('original')
    type = LazyProperty('type')

    status = LazyProperty('status')

    def populate(self, kw):
        for k, v in kw.items():
            if k == 'status' and v == 'processing':
                continue
            setattr(self, k, v)

    def ready_block(self):
        while self.status == "processing":
            time.sleep(1)

    def __init__(self, **kw):
        self.populate(kw)

if __name__ == '__main__':
    import sys, time

    media = Media.upload(sys.argv[1])
    #media = Media.get(sys.argv[1])

    media.ready_block()
    print media.compression, media.original, media.status
