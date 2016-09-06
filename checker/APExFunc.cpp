#define CHECKER_NAME APExFuncChecker
#include "APEx.h"

void ento::registerAPExFuncChecker(CheckerManager &mgr)
{
	mgr.registerChecker<CHECKER_NAME>();
}
