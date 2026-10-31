"""Explicitly enabled, locally installed providers for related reading resources."""
import os
from importlib.metadata import entry_points


class ResourceProviders:
    def __init__(self, config, interface='reader'):
        self.providers = []
        self.interface = interface
        variable = 'CIRDC_WEB_RESOURCE_PROVIDERS' if interface == 'reader' else 'CIRDC_WEB_ADMIN_RESOURCE_PROVIDERS'
        names = [n.strip() for n in os.environ.get(variable, '').split(',') if n.strip()]
        if not names:
            return
        registered = {}
        for item in entry_points(group='cirdc.web_resources'):
            registered.setdefault(item.name, []).append(item)
        for name in dict.fromkeys(names):
            entries = registered.get(name, [])
            if len(entries) != 1:
                raise RuntimeError('An enabled reading-resource provider is missing or ambiguous')
            self.providers.append(entries[0].load()(config))

    def routes(self):
        if getattr(self, 'interface', 'reader') != 'reader':
            return []
        return [route for provider in self.providers for route in provider.routes()]

    def request_policy(self, request):
        if getattr(self, 'interface', 'reader') != 'reader':
            return None
        for provider in self.providers:
            method = getattr(provider, 'request_policy', None)
            if method:
                value = method(request)
                if value is not None:
                    return value
        return None

    def attach(self, items):
        if not self.providers:
            return
        numbers = [str(item['number']) for item in items]
        for item in items:
            item['resources'] = []
        for provider in self.providers:
            try:
                links = provider.links(numbers)
            except Exception:
                for item in items:
                    item['resource_notice'] = '关联资料暂时不可用，请稍后重试。'
                continue
            for item in items:
                item['resources'].extend(links.get(str(item['number']), []))

    def settings(self):
        return [provider.describe_settings() for provider in self.providers
                if callable(getattr(provider, 'describe_settings', None))]

    def configure(self, identifier, values):
        for provider in self.providers:
            if getattr(provider, 'identifier', None) == identifier and callable(getattr(provider, 'configure', None)):
                return provider.configure(values)
        raise ValueError('Unknown configurable resource provider')

    def coverage(self):
        """Optional provider statistics; never expose provider configuration."""
        result = []
        fields = {'id', 'label', 'label_i18n', 'numerator', 'denominator', 'status', 'sampled_at', 'note', 'note_i18n'}
        for provider in self.providers:
            method = getattr(provider, 'coverage', None)
            if not callable(method):
                continue
            try:
                value = method()
                if not isinstance(value, dict):
                    raise TypeError('Invalid resource statistic')
                item = {key: value[key] for key in fields if key in value}
                item.setdefault('id', getattr(provider, 'identifier', 'resources'))
            except Exception:
                item = {'id': getattr(provider, 'identifier', 'resources'), 'status': 'unavailable',
                        'numerator': None, 'label': '阅读资料覆盖率',
                        'label_i18n': {'zh': '阅读资料覆盖率', 'en': 'Reading coverage'}}
            result.append(item)
        return result
