from app.security import is_yookassa_ip


def test_yookassa_ranges_accept_known_hosts() -> None:
    assert is_yookassa_ip("185.71.76.1")
    assert is_yookassa_ip("77.75.156.11")
    assert is_yookassa_ip("77.75.156.35")
    assert is_yookassa_ip("2a02:5180::1")


def test_yookassa_ranges_reject_private() -> None:
    assert not is_yookassa_ip("192.168.1.1")
    assert not is_yookassa_ip("10.0.0.8")
    assert not is_yookassa_ip("not-an-ip")
