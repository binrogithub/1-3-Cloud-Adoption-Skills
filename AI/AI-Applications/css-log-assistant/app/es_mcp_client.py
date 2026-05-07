from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch


@dataclass(frozen=True)
class EsClientConfig:
    es_url: str
    username: Optional[str]
    password: Optional[str]
    insecure: bool
    request_timeout_s: int = 60


class EsClient:
    def __init__(self, config: EsClientConfig):
        http_auth = None
        if config.username and config.password:
            http_auth = (config.username, config.password)
        self._client = Elasticsearch(
            [config.es_url],
            http_auth=http_auth,
            verify_certs=not config.insecure,
            request_timeout=config.request_timeout_s,
        )

    def close(self):
        self._client.transport.close()

    def list_indices(self) -> List[Dict[str, Any]]:
        resp = self._client.cat.indices(format="json")
        return resp

    def get_mappings(self, index: str) -> Dict[str, Any]:
        return self._client.indices.get_mapping(index=index)

    def search(self, index: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.search(index=index, body=body)

