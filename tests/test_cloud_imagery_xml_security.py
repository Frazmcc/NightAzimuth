import pytest
from defusedxml.common import EntitiesForbidden
from nightazimuth.cloud_imagery import parse_wms_layer_times


def test_wms_parser_rejects_entity_expansion():
    payload = b'<!DOCTYPE WMS [<!ENTITY attack "expanded">]><WMS><Layer><Name>&attack;</Name></Layer></WMS>'
    with pytest.raises(EntitiesForbidden):
        parse_wms_layer_times(payload, 'expanded')
