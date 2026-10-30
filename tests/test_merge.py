from app.subscription.merge import deduplicate_links, parse_link

def test_vless_parse():
    parsed = parse_link('vless://1234@example.com:443#main')
    assert parsed is not None
    assert parsed['server'] == 'example.com'
    assert parsed['port'] == 443

def test_deduplicate():
    links = ['vless://1234@example.com:443#one', 'vless://1234@example.com:443#two', 'bad']
    assert len(deduplicate_links(links)) == 1


def _links():
    return [
        'vless://uid@h.example.com:443?security=reality&type=tcp&sni=s.com&fp=chrome&pbk=PK&sid=ab&flow=xtls-rprx-vision#r',
        'trojan://pw@t.example.com:443?sni=t.com#t',
        'hysteria2://pw@y.example.com:8443?sni=y.com#y',
        'ss://YWVzOnB3@s.example.com:8388#s',
    ]


def test_all_formats_render():
    import json, yaml
    from app.subscription.merge import to_clash, to_singbox, to_v2ray_json
    proxies = deduplicate_links(_links())
    assert len(proxies) == 4
    clash = yaml.safe_load(to_clash(proxies))
    assert len(clash['proxies']) == 4
    assert clash['proxies'][0]['reality-opts']['public-key'] == 'PK'
    sb = json.loads(to_singbox(proxies))
    assert {o['type'] for o in sb['outbounds']} == {'vless', 'trojan', 'hysteria2', 'shadowsocks'}
    xr = json.loads(to_v2ray_json(proxies))
    assert xr['outbounds'][0]['streamSettings']['security'] == 'reality'
