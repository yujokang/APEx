#define CHECK_STMT
#define CHECKER_NAME APExStmtChecker
#include "APEx.h"

void
CHECKER_NAME::checkPreStmt(const Stmt *S, CheckerContext &C) const
{
	ProgramStateRef state = C.getState(), tmp_state;
	unsigned n_calls = state->get<TopNCalls>(), new_n_calls = n_calls + 1;

	if ((tmp_state = handleCallerStart(C, state, n_calls)) != NULL) {
		state = tmp_state;
	}
	state = state->set<TopNCalls>(new_n_calls);
	C.addTransition(state);
}


void ento::registerAPExStmtChecker(CheckerManager &mgr)
{
        mgr.registerChecker<CHECKER_NAME>();
}
