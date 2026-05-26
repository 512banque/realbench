The `bank.py` module can hang under concurrent cross-transfers
(e.g. one thread running `transfer(A, B, ...)` while another runs
`transfer(B, A, ...)`). Fix the bug in `bank.py` so the tests in
`test_bank.py` pass without hanging. Do not modify the tests.
