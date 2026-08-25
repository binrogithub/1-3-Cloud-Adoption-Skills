.PHONY: test verify-offline verify-live scan verify-exa-offline verify-exa-live verify-stream-reliability verify-adapter verify-bootstrap verify-thinking-visibility verify-config-protection window-check window-open

test:
	pytest -q

scan:
	python3 scripts/check-prohibited-dependencies.py

verify-adapter:
	pytest -q tests/test_adapter_deploy.py tests/test_lifecycle.py tests/test_adapter_contract.py tests/test_adapter_concurrency.py tests/test_adapter_protocol_security.py

verify-bootstrap:
	pytest -q tests/test_bootstrap.py

verify-config-protection:
	pytest -q tests/test_setup.py tests/test_bootstrap.py tests/test_config_protection_meta.py

verify-offline: scan test

verify-live:
	./scripts/verify.sh

verify-exa-offline:
	pytest -q tests/test_exa_*.py tests/test_verify_exa.py

verify-exa-live:
	./scripts/verify-exa.sh --live

verify-stream-reliability:
	pytest -q tests/test_stream_reliability.py tests/test_stream_reliability_integration.py

verify-thinking-visibility:
	pytest -q tests/test_thinking_visibility.py

# PRD RELEASE_V12 release gates: N1-G (single listener), N2-G (capture
# offline), N4-G (/status == journald request_end). N5 is a time gate.
window-check:
	bash scripts/window-check-v12.sh

# Open/refresh the v1.2 soak window (records baseline + commit).
window-open:
	bash scripts/window-check-v12.sh --record
