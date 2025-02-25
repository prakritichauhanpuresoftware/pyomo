import pyomo.environ as pe
from pyomo.common.dependencies import attempt_import
import pyomo.common.unittest as unittest
parameterized, param_available = attempt_import('parameterized')
if not param_available:
    raise unittest.SkipTest('Parameterized is not available.')
parameterized = parameterized.parameterized
try:
    from pyomo.contrib.appsi.cmodel import cmodel
except ImportError:
    raise unittest.SkipTest('appsi extensions are not available')
from pyomo.contrib.appsi.base import TerminationCondition, Results, PersistentSolver
from pyomo.contrib.appsi.solvers import Gurobi, Ipopt, Cplex, Cbc
from typing import Type
from pyomo.core.expr.numeric_expr import LinearExpression
import os


all_solvers = [('gurobi', Gurobi), ('ipopt', Ipopt), ('cplex', Cplex), ('cbc', Cbc)]
mip_solvers = [('gurobi', Gurobi), ('cplex', Cplex), ('cbc', Cbc)]
nlp_solvers = [('ipopt', Ipopt)]
qcp_solvers = [('gurobi', Gurobi), ('ipopt', Ipopt), ('cplex', Cplex)]
miqcqp_solvers = [('gurobi', Gurobi), ('cplex', Cplex)]


"""
The tests in this file are used to ensure basic functionality/API works with all solvers

Feature                                    Tested
-------                                    ------
config time_limit                          
config tee                                 
config load_solution True                  x
config load_solution False                 x     
results termination condition optimal      x
results termination condition infeasible   x
load_vars                                  
get_duals                                  x
get_reduced_costs                          x
range constraints                          x
MILP
Model updates - added constriants          x
Model updates - removed constraints        x
Model updates - added vars
Model updates - removed vars
Model updates - changed named expression
Model updates - mutable param modified     x
Model updates - var modified
Model updates - objective changed
Model updates - constraint modified
No objective
No constraints                             x
bounds                                     x
best feasible objective                    x
best objective bound                       x
fixed variables
"""


class TestSolvers(unittest.TestCase):
    @parameterized.expand(input=all_solvers)
    def test_range_constraint(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.obj = pe.Objective(expr=m.x)
        m.c = pe.Constraint(expr=(-1, m.x, 1))
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, -1)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c], 1)
        m.obj.sense = pe.maximize
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, 1)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c], 1)

    @parameterized.expand(input=all_solvers)
    def test_reduced_costs(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var(bounds=(-1, 1))
        m.y = pe.Var(bounds=(-2, 2))
        m.obj = pe.Objective(expr=3*m.x + 4*m.y)
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, -1)
        self.assertAlmostEqual(m.y.value, -2)
        rc = opt.get_reduced_costs()
        self.assertAlmostEqual(rc[m.x], 3)
        self.assertAlmostEqual(rc[m.y], 4)

    @parameterized.expand(input=all_solvers)
    def test_reduced_costs2(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var(bounds=(-1, 1))
        m.obj = pe.Objective(expr=m.x)
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, -1)
        rc = opt.get_reduced_costs()
        self.assertAlmostEqual(rc[m.x], 1)
        m.obj.sense = pe.maximize
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, 1)
        rc = opt.get_reduced_costs()
        self.assertAlmostEqual(rc[m.x], 1)

    @parameterized.expand(input=all_solvers)
    def test_param_changes(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(mutable=True)
        m.a2 = pe.Param(mutable=True)
        m.b1 = pe.Param(mutable=True)
        m.b2 = pe.Param(mutable=True)
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=(0, m.y - m.a1*m.x - m.b1, None))
        m.c2 = pe.Constraint(expr=(None, -m.y + m.a2*m.x + m.b2, 0))

        params_to_test = [(1, -1, 2, 1), (1, -2, 2, 1), (1, -1, 3, 1)]
        for (a1, a2, b1, b2) in params_to_test:
            m.a1.value = a1
            m.a2.value = a2
            m.b1.value = b1
            m.b2.value = b2
            res: Results = opt.solve(m)
            self.assertEqual(res.termination_condition, TerminationCondition.optimal)
            self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
            self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
            self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
            self.assertTrue(res.best_objective_bound <= m.y.value)
            duals = opt.get_duals()
            self.assertAlmostEqual(duals[m.c1], (1 + a1 / (a2 - a1)))
            self.assertAlmostEqual(duals[m.c2], a1 / (a2 - a1))

    @parameterized.expand(input=all_solvers)
    def test_equality(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(mutable=True)
        m.a2 = pe.Param(mutable=True)
        m.b1 = pe.Param(mutable=True)
        m.b2 = pe.Param(mutable=True)
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=m.y == m.a1 * m.x + m.b1)
        m.c2 = pe.Constraint(expr=m.y == m.a2 * m.x + m.b2)

        params_to_test = [(1, -1, 2, 1), (1, -2, 2, 1), (1, -1, 3, 1)]
        for (a1, a2, b1, b2) in params_to_test:
            m.a1.value = a1
            m.a2.value = a2
            m.b1.value = b1
            m.b2.value = b2
            res: Results = opt.solve(m)
            self.assertEqual(res.termination_condition, TerminationCondition.optimal)
            self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
            self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
            self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
            self.assertTrue(res.best_objective_bound <= m.y.value)
            duals = opt.get_duals()
            self.assertAlmostEqual(duals[m.c1], (1 + a1 / (a2 - a1)))
            self.assertAlmostEqual(duals[m.c2], -a1 / (a2 - a1))

    @parameterized.expand(input=all_solvers)
    def test_linear_expression(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(mutable=True)
        m.a2 = pe.Param(mutable=True)
        m.b1 = pe.Param(mutable=True)
        m.b2 = pe.Param(mutable=True)
        m.obj = pe.Objective(expr=m.y)
        e = LinearExpression(constant=m.b1, linear_coefs=[-1, m.a1], linear_vars=[m.y, m.x])
        m.c1 = pe.Constraint(expr=e == 0)
        e = LinearExpression(constant=m.b2, linear_coefs=[-1, m.a2], linear_vars=[m.y, m.x])
        m.c2 = pe.Constraint(expr=e == 0)

        params_to_test = [(1, -1, 2, 1), (1, -2, 2, 1), (1, -1, 3, 1)]
        for (a1, a2, b1, b2) in params_to_test:
            m.a1.value = a1
            m.a2.value = a2
            m.b1.value = b1
            m.b2.value = b2
            res: Results = opt.solve(m)
            self.assertEqual(res.termination_condition, TerminationCondition.optimal)
            self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
            self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
            self.assertTrue(res.best_objective_bound <= m.y.value)

    @parameterized.expand(input=all_solvers)
    def test_no_objective(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(mutable=True)
        m.a2 = pe.Param(mutable=True)
        m.b1 = pe.Param(mutable=True)
        m.b2 = pe.Param(mutable=True)
        m.c1 = pe.Constraint(expr=m.y == m.a1 * m.x + m.b1)
        m.c2 = pe.Constraint(expr=m.y == m.a2 * m.x + m.b2)
        opt.config.stream_solver = True

        params_to_test = [(1, -1, 2, 1), (1, -2, 2, 1), (1, -1, 3, 1)]
        for (a1, a2, b1, b2) in params_to_test:
            m.a1.value = a1
            m.a2.value = a2
            m.b1.value = b1
            m.b2.value = b2
            res: Results = opt.solve(m)
            self.assertEqual(res.termination_condition, TerminationCondition.optimal)
            self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
            self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
            self.assertEqual(res.best_feasible_objective, None)
            self.assertEqual(res.best_objective_bound, None)
            duals = opt.get_duals()
            self.assertAlmostEqual(duals[m.c1], 0)
            self.assertAlmostEqual(duals[m.c2], 0)

    @parameterized.expand(input=all_solvers)
    def test_add_remove_cons(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        a1 = -1
        a2 = 1
        b1 = 1
        b2 = 2
        a3 = 1
        b3 = 3
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=m.y >= a1 * m.x + b1)
        m.c2 = pe.Constraint(expr=m.y >= a2 * m.x + b2)
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
        self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
        self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
        self.assertTrue(res.best_objective_bound <= m.y.value)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c1], -(1 + a1 / (a2 - a1)))
        self.assertAlmostEqual(duals[m.c2], a1 / (a2 - a1))

        m.c3 = pe.Constraint(expr=m.y >= a3 * m.x + b3)
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, (b3 - b1) / (a1 - a3))
        self.assertAlmostEqual(m.y.value, a1 * (b3 - b1) / (a1 - a3) + b1)
        self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
        self.assertTrue(res.best_objective_bound <= m.y.value)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c1], -(1 + a1 / (a3 - a1)))
        self.assertAlmostEqual(duals[m.c2], 0)
        self.assertAlmostEqual(duals[m.c3], a1 / (a3 - a1))

        del m.c3
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
        self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
        self.assertAlmostEqual(res.best_feasible_objective, m.y.value)
        self.assertTrue(res.best_objective_bound <= m.y.value)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c1], -(1 + a1 / (a2 - a1)))
        self.assertAlmostEqual(duals[m.c2], a1 / (a2 - a1))

    @parameterized.expand(input=all_solvers)
    def test_results_infeasible(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=m.y >= m.x)
        m.c2 = pe.Constraint(expr=m.y <= m.x - 1)
        with self.assertRaises(Exception):
            res = opt.solve(m)
        opt.config.load_solution = False
        res = opt.solve(m)
        self.assertNotEqual(res.termination_condition, TerminationCondition.optimal)
        if opt_class is Ipopt:
            acceptable_termination_conditions = {TerminationCondition.infeasible,
                                                 TerminationCondition.unbounded}
        else:
            acceptable_termination_conditions = {TerminationCondition.infeasible,
                                                 TerminationCondition.infeasibleOrUnbounded}
        self.assertIn(res.termination_condition, acceptable_termination_conditions)
        self.assertAlmostEqual(m.x.value, None)
        self.assertAlmostEqual(m.y.value, None)
        self.assertTrue(res.best_feasible_objective is None)

    @parameterized.expand(input=all_solvers)
    def test_duals(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=m.y - m.x >= 0)
        m.c2 = pe.Constraint(expr=m.y + m.x - 2 >= 0)

        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 1)
        self.assertAlmostEqual(m.y.value, 1)
        duals = opt.get_duals()
        self.assertAlmostEqual(duals[m.c1], 0.5)
        self.assertAlmostEqual(duals[m.c2], 0.5)

        duals = opt.get_duals(cons_to_load=[m.c1])
        self.assertAlmostEqual(duals[m.c1], 0.5)
        self.assertNotIn(m.c2, duals)

    @parameterized.expand(input=qcp_solvers)
    def test_mutable_quadratic_coefficient(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a = pe.Param(initialize=1, mutable=True)
        m.b = pe.Param(initialize=-1, mutable=True)
        m.obj = pe.Objective(expr=m.x**2 + m.y**2)
        m.c = pe.Constraint(expr=m.y >= (m.a*m.x + m.b)**2)

        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0.41024548525899274, 4)
        self.assertAlmostEqual(m.y.value, 0.34781038127030117, 4)
        m.a.value = 2
        m.b.value = -0.5
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0.10256137418973625, 4)
        self.assertAlmostEqual(m.y.value, 0.0869525991355825, 4)

    @parameterized.expand(input=qcp_solvers)
    def test_mutable_quadratic_objective(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a = pe.Param(initialize=1, mutable=True)
        m.b = pe.Param(initialize=-1, mutable=True)
        m.c = pe.Param(initialize=1, mutable=True)
        m.d = pe.Param(initialize=1, mutable=True)
        m.obj = pe.Objective(expr=m.x**2 + m.c*m.y**2 + m.d*m.x)
        m.ccon = pe.Constraint(expr=m.y >= (m.a*m.x + m.b)**2)

        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0.2719178742733325, 4)
        self.assertAlmostEqual(m.y.value, 0.5301035741688002, 4)
        m.c.value = 3.5
        m.d.value = -1
        res = opt.solve(m)

        self.assertAlmostEqual(m.x.value, 0.6962249634573562, 4)
        self.assertAlmostEqual(m.y.value, 0.09227926676152151, 4)

    @parameterized.expand(input=all_solvers)
    def test_fixed_vars(self, namee: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.x.fix(0)
        m.y = pe.Var()
        a1 = 1
        a2 = -1
        b1 = 1
        b2 = 2
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=m.y >= a1 * m.x + b1)
        m.c2 = pe.Constraint(expr=m.y >= a2 * m.x + b2)
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0)
        self.assertAlmostEqual(m.y.value, 2)
        m.x.unfix()
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
        self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
        m.x.fix(0)
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0)
        self.assertAlmostEqual(m.y.value, 2)
        m.x.value = 2
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 2)
        self.assertAlmostEqual(m.y.value, 3)
        m.x.value = 0
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0)
        self.assertAlmostEqual(m.y.value, 2)

    @parameterized.expand(input=all_solvers)
    def test_mutable_param_with_range(self, name: str, opt_class: Type[PersistentSolver]):
        opt: PersistentSolver = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        try:
            import numpy as np
        except:
            raise unittest.SkipTest('numpy is not available')
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(initialize=0, mutable=True)
        m.a2 = pe.Param(initialize=0, mutable=True)
        m.b1 = pe.Param(initialize=0, mutable=True)
        m.b2 = pe.Param(initialize=0, mutable=True)
        m.c1 = pe.Param(initialize=0, mutable=True)
        m.c2 = pe.Param(initialize=0, mutable=True)
        m.obj = pe.Objective(expr=m.y)
        m.con1 = pe.Constraint(expr=(m.b1, m.y - m.a1 * m.x, m.c1))
        m.con2 = pe.Constraint(expr=(m.b2, m.y - m.a2 * m.x, m.c2))

        np.random.seed(0)
        params_to_test = [(np.random.uniform(0, 10), np.random.uniform(-10, 0),
                           np.random.uniform(-5, 2.5), np.random.uniform(-5, 2.5),
                           np.random.uniform(2.5, 10), np.random.uniform(2.5, 10), pe.minimize),
                          (np.random.uniform(0, 10), np.random.uniform(-10, 0),
                           np.random.uniform(-5, 2.5), np.random.uniform(-5, 2.5),
                           np.random.uniform(2.5, 10), np.random.uniform(2.5, 10), pe.maximize),
                          (np.random.uniform(0, 10), np.random.uniform(-10, 0),
                           np.random.uniform(-5, 2.5), np.random.uniform(-5, 2.5),
                           np.random.uniform(2.5, 10), np.random.uniform(2.5, 10), pe.minimize),
                          (np.random.uniform(0, 10), np.random.uniform(-10, 0),
                           np.random.uniform(-5, 2.5), np.random.uniform(-5, 2.5),
                           np.random.uniform(2.5, 10), np.random.uniform(2.5, 10), pe.maximize)]
        for (a1, a2, b1, b2, c1, c2, sense) in params_to_test:
            m.a1.value = float(a1)
            m.a2.value = float(a2)
            m.b1.value = float(b1)
            m.b2.value = float(b2)
            m.c1.value = float(c1)
            m.c2.value = float(c2)
            m.obj.sense = sense
            res: Results = opt.solve(m)
            self.assertEqual(res.termination_condition, TerminationCondition.optimal)
            if sense is pe.minimize:
                self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2), 6)
                self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1, 6)
                self.assertAlmostEqual(res.best_feasible_objective, m.y.value, 6)
                self.assertTrue(res.best_objective_bound <= m.y.value + 1e-12)
                duals = opt.get_duals()
                self.assertAlmostEqual(duals[m.con1], (1 + a1 / (a2 - a1)), 6)
                self.assertAlmostEqual(duals[m.con2], -a1 / (a2 - a1), 6)
            else:
                self.assertAlmostEqual(m.x.value, (c2 - c1) / (a1 - a2), 6)
                self.assertAlmostEqual(m.y.value, a1 * (c2 - c1) / (a1 - a2) + c1, 6)
                self.assertAlmostEqual(res.best_feasible_objective, m.y.value, 6)
                self.assertTrue(res.best_objective_bound >= m.y.value - 1e-12)
                duals = opt.get_duals()
                self.assertAlmostEqual(duals[m.con1], (1 + a1 / (a2 - a1)), 6)
                self.assertAlmostEqual(duals[m.con2], -a1 / (a2 - a1), 6)

    @parameterized.expand(input=all_solvers)
    def test_add_and_remove_vars(self, name: str, opt_class: Type[PersistentSolver]):
        opt = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.y = pe.Var(bounds=(-1, None))
        m.obj = pe.Objective(expr=m.y)
        opt.update_config.update_params = False
        opt.update_config.update_vars = False
        opt.update_config.update_constraints = False
        opt.update_config.update_named_expressions = False
        opt.update_config.check_for_new_or_removed_params = False
        opt.update_config.check_for_new_or_removed_constraints = False
        opt.update_config.check_for_new_or_removed_vars = False
        opt.config.load_solution = False
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        opt.load_vars()
        self.assertAlmostEqual(m.y.value, -1)
        m.x = pe.Var()
        a1 = 1
        a2 = -1
        b1 = 2
        b2 = 1
        m.c1 = pe.Constraint(expr=(0, m.y - a1*m.x-b1, None))
        m.c2 = pe.Constraint(expr=(None, -m.y + a2*m.x+b2, 0))
        opt.add_variables([m.x])
        opt.add_constraints([m.c1, m.c2])
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        opt.load_vars()
        self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
        self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
        opt.remove_constraints([m.c1, m.c2])
        opt.remove_variables([m.x])
        m.x.value = None
        res = opt.solve(m)
        self.assertEqual(res.termination_condition, TerminationCondition.optimal)
        opt.load_vars()
        self.assertEqual(m.x.value, None)
        self.assertAlmostEqual(m.y.value, -1)
        with self.assertRaises(Exception):
            opt.load_vars([m.x])

    @parameterized.expand(input=nlp_solvers)
    def test_exp(self, name: str, opt_class: Type[PersistentSolver]):
        opt = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.obj = pe.Objective(expr=m.x**2 + m.y**2)
        m.c1 = pe.Constraint(expr=m.y >= pe.exp(m.x))
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, -0.42630274815985264)
        self.assertAlmostEqual(m.y.value, 0.6529186341994245)

    @parameterized.expand(input=nlp_solvers)
    def test_log(self, name: str, opt_class: Type[PersistentSolver]):
        opt = opt_class()
        if not opt.available():
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var(initialize=1)
        m.y = pe.Var()
        m.obj = pe.Objective(expr=m.x**2 + m.y**2)
        m.c1 = pe.Constraint(expr=m.y <= pe.log(m.x))
        res = opt.solve(m)
        self.assertAlmostEqual(m.x.value, 0.6529186341994245)
        self.assertAlmostEqual(m.y.value, -0.42630274815985264)


class TestLegacySolverInterface(unittest.TestCase):
    @parameterized.expand(input=all_solvers)
    def test_param_updates(self, name: str, opt_class: Type[PersistentSolver]):
        opt = pe.SolverFactory('appsi_' + name)
        if not opt.available(exception_flag=False):
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.y = pe.Var()
        m.a1 = pe.Param(mutable=True)
        m.a2 = pe.Param(mutable=True)
        m.b1 = pe.Param(mutable=True)
        m.b2 = pe.Param(mutable=True)
        m.obj = pe.Objective(expr=m.y)
        m.c1 = pe.Constraint(expr=(0, m.y - m.a1*m.x - m.b1, None))
        m.c2 = pe.Constraint(expr=(None, -m.y + m.a2*m.x + m.b2, 0))
        m.dual = pe.Suffix(direction=pe.Suffix.IMPORT)

        params_to_test = [(1, -1, 2, 1), (1, -2, 2, 1), (1, -1, 3, 1)]
        for (a1, a2, b1, b2) in params_to_test:
            m.a1.value = a1
            m.a2.value = a2
            m.b1.value = b1
            m.b2.value = b2
            res = opt.solve(m)
            pe.assert_optimal_termination(res)
            self.assertAlmostEqual(m.x.value, (b2 - b1) / (a1 - a2))
            self.assertAlmostEqual(m.y.value, a1 * (b2 - b1) / (a1 - a2) + b1)
            self.assertAlmostEqual(m.dual[m.c1], (1 + a1 / (a2 - a1)))
            self.assertAlmostEqual(m.dual[m.c2], a1 / (a2 - a1))

    @parameterized.expand(input=all_solvers)
    def test_load_solutions(self, name: str, opt_class: Type[PersistentSolver]):
        opt = pe.SolverFactory('appsi_' + name)
        if not opt.available(exception_flag=False):
            raise unittest.SkipTest
        m = pe.ConcreteModel()
        m.x = pe.Var()
        m.obj = pe.Objective(expr=m.x)
        m.c = pe.Constraint(expr=(-1, m.x, 1))
        m.dual = pe.Suffix(direction=pe.Suffix.IMPORT)
        res = opt.solve(m, load_solutions=False)
        pe.assert_optimal_termination(res)
        self.assertIsNone(m.x.value)
        self.assertNotIn(m.c, m.dual)
        m.solutions.load_from(res)
        self.assertAlmostEqual(m.x.value, -1)
        self.assertAlmostEqual(m.dual[m.c], 1)
