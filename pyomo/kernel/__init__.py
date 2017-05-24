#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

import pyomo.environ
from pyomo.core.kernel import *
import pyomo.core.kernel as kernel

# set up the Block ctype
from pyomo.core.base import Block
block._ctype = Block
block_tuple._ctype = Block
block_list._ctype = Block
block_dict._ctype = Block
tiny_block._ctype = Block
del Block

# set up the Var ctype
from pyomo.core.base import Var
variable._ctype = Var
variable_tuple._ctype = Var
variable_list._ctype = Var
variable_dict._ctype = Var
del Var

# set up the Constraint ctype
from pyomo.core.base import Constraint
from pyomo.core.kernel.component_matrix_constraint \
    import _MatrixConstraintData
constraint._ctype = Constraint
linear_constraint._ctype = Constraint
constraint_tuple._ctype = Constraint
constraint_list._ctype = Constraint
constraint_dict._ctype = Constraint
_MatrixConstraintData._ctype = Constraint
matrix_constraint._ctype = Constraint
del _MatrixConstraintData
del Constraint

# set up the Param ctype
from pyomo.core.base import Param
parameter._ctype = Param
parameter_tuple._ctype = Param
parameter_list._ctype = Param
parameter_dict._ctype = Param
del Param

# set up the Expression ctype
from pyomo.core.base import Expression
expression._ctype = Expression
data_expression._ctype = Expression
expression_tuple._ctype = Expression
expression_list._ctype = Expression
expression_dict._ctype = Expression
del Expression

# set up the Objective ctype
from pyomo.core.base import Objective
objective._ctype = Objective
objective_tuple._ctype = Objective
objective_list._ctype = Objective
objective_dict._ctype = Objective
del Objective

# set up the SOSConstraint ctype
from pyomo.core.base import SOSConstraint
sos._ctype = SOSConstraint
sos_tuple._ctype = SOSConstraint
sos_list._ctype = SOSConstraint
sos_dict._ctype = SOSConstraint
del SOSConstraint

# set up the Suffix ctype
from pyomo.core.base import Suffix
suffix._ctype = Suffix
del Suffix
