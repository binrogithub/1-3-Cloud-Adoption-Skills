import importlib.machinery
import importlib.util
import pathlib


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "delegate"
loader = importlib.machinery.SourceFileLoader("oauth_delegate", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
delegate = importlib.util.module_from_spec(spec)
loader.exec_module(delegate)


def test_attempt_ceiling():
    assert delegate.bounded_attempts(0) == 1
    assert delegate.bounded_attempts(1) == 1
    assert delegate.bounded_attempts(2) == 2
    assert delegate.bounded_attempts(99) == 2


def test_429_backoff_is_bounded():
    delay = delegate.retry_delay(
        1,
        {"summary": "HTTP 429 Too Many Requests; Retry-After: 120"},
        "",
    )
    assert delay == delegate.MAX_BACKOFF
    assert delegate.retry_delay(1, {"summary": "ordinary test failure"}, "") == 0


if __name__ == "__main__":
    test_attempt_ceiling()
    test_429_backoff_is_bounded()
    print("delegate safety tests passed")
