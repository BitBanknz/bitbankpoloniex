"""Run old outcome regressions and new boundaries against packaged modules."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'worker'))
import outcomes
import prefix
assert Path(outcomes.__file__).resolve() == HERE / 'worker/outcomes.py'
assert Path(prefix.__file__).resolve() == HERE / 'worker/prefix.py'
assert (HERE / 'worker/outcomes.py').read_bytes() == (HERE / 'outcomes.py').read_bytes()
assert (HERE / 'worker/prefix.py').read_bytes() == (HERE / 'prefix.py').read_bytes()
suite = unittest.TestSuite()
for name, path in [('original', HERE.parent / 'futureworker20260926/test_outcomes.py'),
                   ('waiting', HERE / 'test_waiting.py'), ('prefix_regression', HERE / 'test_prefix.py')]:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if name != 'prefix_regression':
        assert module.completed_cycle is outcomes.completed_cycle
    else:
        assert module.Prefix is prefix.Prefix
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
