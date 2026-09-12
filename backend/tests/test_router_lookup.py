from app.services import mc_router


def test_lookup_exact_and_short_name() -> None:
    mc_router._backends.clear()
    mc_router.register("alpha.shnenepepe.ru", 25566)
    mc_router.register("beta.shnenepepe.ru", 25567)
    assert mc_router.lookup("alpha.shnenepepe.ru").port == 25566
    assert mc_router.lookup("beta").port == 25567
    assert mc_router.lookup("unknown.example") is None


def test_lookup_does_not_fallback_to_first() -> None:
    mc_router._backends.clear()
    mc_router.register("one.shnenepepe.ru", 25566)
    mc_router.register("two.shnenepepe.ru", 25567)
    assert mc_router.lookup("192.168.0.7") is None
    assert mc_router.lookup("127.0.0.1") is None
    mc_router.register("192.168.0.7", 25566)
    assert mc_router.lookup("192.168.0.7").port == 25566
