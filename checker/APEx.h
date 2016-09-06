/*
 * the generic checker code for both function and statement counts
 * Before including this header file, define the macro `CHECKER_NAME`
 * to be the name of the checker class.
 * Also, if the checker counts statements,
 * define the macro CHECK_STMT
 */
#ifndef APEX_H
#define APEX_H

#ifndef CHECKER_NAME
#error "Please define the CHECKER_NAME macro"
#endif

#include "ClangSACheckers.h"
#include "clang/StaticAnalyzer/Core/BugReporter/BugType.h"
#include "clang/StaticAnalyzer/Core/Checker.h"
#include "clang/StaticAnalyzer/Core/PathSensitive/CallEvent.h"
#include "clang/StaticAnalyzer/Core/PathSensitive/CheckerContext.h"
#include <unistd.h>
#include <string.h>
#include <stdio.h>

#define OUT_STREAM llvm::errs()

using namespace clang;
using namespace ento;

/* maximum number of bits supported for integers */
#define MAX_ACTIVE_BITS 64

namespace {
	/*
	 * Extract the exact integer value if the APSInt object is small enough.
	 * int_val: holds the integer value
	 * ret: if int_val does not have too many active bits,
	 *	the integer value is stored here.
	 * returns true iff int_val's integer value was extracted
	 */
	bool getAPSInt(const llvm::APSInt &int_val, int64_t *ret)
	{
		if (int_val.getActiveBits() <= MAX_ACTIVE_BITS) {
			*ret = int_val.getExtValue();
			return true;
		} else {
			return false;
		}
	}

	/*
	 * Try to extract the exact integer value.
	 * val: the object representing an integer value
	 * ret: in case of success, the integer value is stored here
	 * returns true iff val has an exact integer value that fits in ret
	 */
	bool getConcreteValue(SVal val, int64_t *ret)
	{
		Optional<loc::ConcreteInt> LV = val.getAs<loc::ConcreteInt>();
		Optional<nonloc::ConcreteInt> NV;

		if (LV) {
			return getAPSInt(LV->getValue(), ret);
		}

		NV = val.getAs<nonloc::ConcreteInt>();
		if (NV) {
			return getAPSInt(NV->getValue(), ret);
		}

		return false;
	}

	/* value types */
	enum s_type {
		INT_TYPE, /* integer */
		BOOL_TYPE, /* C++ bool */
		PTR_TYPE, /* pointer */
		N_TYPES /* number of valid types, and also an invalid type */
	};

	/*
	 * Extract the type.
	 * type_struct: the type object
	 * returns the recognized type enum, or N_TYPES if it is not known
	 */
	enum s_type getType(QualType type_struct)
	{
		enum s_type type = N_TYPES;

		if (type_struct->isIntegerType()) {
			type = INT_TYPE;
		} else if (type_struct->isBooleanType()) {
			type = BOOL_TYPE;
		} else if (type_struct->isPointerType()) {
			type = PTR_TYPE;
		}

		return type;
	}

	/* maps the type enum to its marker */
	const static char
	type_tags[N_TYPES] = {[INT_TYPE] = 'I', [BOOL_TYPE] = 'B',
			      [PTR_TYPE] = 'P'};
/* the void type */
#define VOID_TYPE	"V"

	/* for binary types, maps to string representation of non-zero value */
	const static char
	*nonzero_markers[N_TYPES] = {[INT_TYPE] = NULL, [BOOL_TYPE] = "true",
				     [PTR_TYPE] = "notnull"};
	/* for binary types, maps to string representation of zero value */
	const static char
	*zero_markers[N_TYPES] = {[INT_TYPE] = NULL, [BOOL_TYPE] = "false",
				  [PTR_TYPE] = "null"};

/*
 * If the binary type is unknown,
 * this string is between both possible value strings.
 */
#define UNKNOWN_DELIM "or"

/* marker denoting assignment */
#define ASSIGN		":="
/* marker denoting end of assignment */
#define INT_ASSIGN_END	"\\"
/* prefix denoting if value is a symbol */
#define SYMBOL_PRE	"&"

	/*
	 * Print a value.
	 * value: the value to print
	 * type: the value's type
	 * C: the context holding the state for finding the value to print
	 * out: the output stream to print to
	 */
	void printValue(SVal value, enum s_type type, CheckerContext &C,
			raw_ostream &out)
	{
		const SymExpr *sexpr = value.getAsSymExpr();
		ProgramStateRef state = C.getState();

		/* Exit on invalid type. */
		if (type < 0 || N_TYPES <= type) {
			return;
		}
		/* Print the type. */
		out << type_tags[type];

		/* Print the symbol if it exists. */
		if (sexpr != NULL) {
			out << SYMBOL_PRE;
			sexpr->dumpToStream(out);
			out << ASSIGN;
		}

		switch(type) {
		case INT_TYPE: {
			/* Print the integer range. */
			int64_t real_val;
			if (getConcreteValue(value, &real_val)) {
				out << std::to_string(real_val);
			} else {
				if (sexpr != NULL) {
					SymExpr::symbol_iterator symbol_i,
								 symbol_end;
					ConstraintManager
					&CM = C.getConstraintManager();
					for (symbol_i = sexpr->symbol_begin(),
					     symbol_end = sexpr->symbol_end();
					     symbol_i != symbol_end;
					     ++symbol_i) {
						(*symbol_i)->dumpToStream(out);
						out << ASSIGN;
						CM.print(state, out,
							 "\n", " ", *symbol_i);
						out << INT_ASSIGN_END;
					}
				}
			}
			break;
		}
		/*
		 * For binary types, print if the value is equal to
		 * 0, or not, or maybe.
		 */
		case BOOL_TYPE:
		case PTR_TYPE: {
			if (value.isUndef()) {
				out << nonzero_markers[type];
				out << UNKNOWN_DELIM;
				out << zero_markers[type];
			} else {
				ProgramStateRef state_nonzero, state_zero;
				std::tie(state_nonzero, state_zero) =
				state->assume(value.
					      castAs<DefinedOrUnknownSVal>());
				bool nonzero_possible = !!state_nonzero;

				if (nonzero_possible) {
					out << nonzero_markers[type];
				}

				if (state_zero) {
					if (nonzero_possible) {
						out << UNKNOWN_DELIM;
					}
					out << zero_markers[type];
				}
			}
		}
		default:
			/* this case should never happen */
			break;
		}
	}

	/*
	 * Check if a value is exactly known.
	 * val: the value to check if it is known
	 * returns true if the value is exactly known,
	 *	   ie. it does not have a symbol
	 */
	static bool isFixed(SVal val)
	{
		return !val.getAsSymExpr();
	}

	/*
	 * status about what has been displayed or seen during path exploration
	 * of a function
	 */
	struct SimpleStatus {
	private:
		bool printed; /* Has anything been seen in this function? */
		bool seen; /* Has a call been seen? */
		/* the stack depth when this object was created */
		unsigned depth;
	public:
		/*
		 * p: printed
		 * s: seen
		 * d: depth
		 */
		SimpleStatus(bool p, bool s, unsigned d) :
		printed(p), seen(s), depth(d)
		{
		}

		bool operator==(const SimpleStatus &X) const
		{
			return (X.printed == printed) &&
			       (X.seen == seen) &&
			       (X.depth == depth);
		}

		/*
		 * Get printed.
		 * returns printed
		 */
		bool isPrinted() const
		{
			return printed;
		}

		/*
		 * Get seen.
		 * returns seen
		 */
		bool isSeen() const
		{
			return seen;
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddBoolean(printed);
			ID.AddBoolean(seen);
			ID.AddInteger(depth);
		}
	};

	/* status of entries in stack */
	struct StackRow {
	private:
		unsigned n_entries; /* number of entries */
		bool printed; /* have the entries been printed? */
	public:
		/*
		 * n_e: n_entries
		 * p: printed
		 */
		StackRow(unsigned n_e = 0, bool p = false) :
		n_entries(n_e), printed(p)
		{
		}

		/*
		 * Get n_entries.
		 * returns n_entries
		 */
		unsigned getNEntries() const
		{
			return n_entries;
		}

		/*
		 * Get printed.
		 * returns printed
		 */
		bool isPrinted() const
		{
			return printed;
		}

		bool operator==(const StackRow &X) const
		{
			return (X.n_entries == n_entries) &&
			       (X.printed == printed);
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddInteger(n_entries);
			ID.AddInteger(printed);
		}
	};

	/* the key to access a layer in the stack */
	struct StackKey
	{
	private:
		unsigned stack_depth; /* the depth of the layer */
	public:
		/*
		 * s_d: stack_depth
		 */
		StackKey(unsigned s_d) : stack_depth(s_d)
		{
		}

		bool operator==(const StackKey &X) const
		{
			return (X.stack_depth == stack_depth);
		}

		bool operator<(const StackKey &X) const
		{
			return (X.stack_depth < stack_depth);
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddInteger(stack_depth);
		}
	};

	/* the key to access an entry within the layer of a stack */
	struct StackRowKey
	{
	private:
		unsigned stack_depth; /* the depth of the layer */
		unsigned index; /* the entry index */
	public:
		/*
		 * s_d: stack_depth
		 * index: idx
		 */
		StackRowKey(unsigned s_d, unsigned idx) :
		stack_depth(s_d), index(idx)
		{
		}

		/*
		 * Get stack_depth.
		 * returns stack_depth
		 */
		unsigned getStackDepth()
		{
			return stack_depth;
		}

		/*
		 * Get index.
		 * returns index
		 */
		unsigned getIndex()
		{
			return index;
		}

		bool operator==(const StackRowKey &X) const
		{
			return (X.stack_depth == stack_depth) &&
			       (X.index == index);
		}

		bool operator<(const StackRowKey &X) const
		{
			if (X.stack_depth < stack_depth) {
				return true;
			} else if (X.stack_depth == stack_depth) {
				return X.index < index;
			}
			return false;
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddInteger(stack_depth);
			ID.AddInteger(index);
		}
	};

	/*
	 * Keeps track of number of calls or statementns (originally calls)
	 * within a function.
	 */
	struct NCalls {
		private:
			/* the number of calls or statements */
			unsigned n_calls;
			/* the stack depth when the function is executed */
			unsigned stack_depth;
		public:
			/*
			 * n_c: n_calls
			 * s_d: stack_depth
			 */
			NCalls(unsigned n_c, unsigned s_d) : n_calls(n_c),
			stack_depth(s_d)
			{
			}

			bool operator==(const NCalls &X) const
			{
				return (X.n_calls == n_calls) &&
					(X.stack_depth == stack_depth);
			}

			void Profile(llvm::FoldingSetNodeID &ID) const
			{
				ID.AddInteger(n_calls);
				ID.AddInteger(stack_depth);
			}

			/*
			 * Get n_calls.
			 * returns n_calls
			 */
			unsigned getNCalls() const
			{
				return n_calls;
			}

			/*
			 * Get stack_depth.
			 * returns stack_depth
			 */
			unsigned getStackDepth() const
			{
				return stack_depth;
			}
	};

	/*
	 * Keeps track of the last-known value of a symbol.
	 */
	struct CurrentSymbolValue {
	private:
		/*
		 * the creation time of this struct,
		 * to keep it unique in the state
		 */
		clock_t creation_time;
		/* the type of the value */
		enum s_type type;
		/* Is the value exactly known? */
		bool known;
		/*
		 * the string representation of the value,
		 * if it is exactly known
		 */
		std::string concrete_value;
		/* the symbol containing the value */
		SVal symbolic_value;

		/*
		 * Save the value string, if it exactly known or dead,
		 * or the symbol otherwise.
		 * s_v: the symbol that may contain the value
		 * C: the context for printing the value, if it is known
		 * alive: is the symbol still alive?
		 */
		void initValue(SVal s_v, CheckerContext &C, bool alive)
		{
			if (!isFixed(s_v) && alive) {
				known = false;
				symbolic_value = s_v;
			} else {
				llvm::raw_string_ostream
					string_out(concrete_value);

				known = true;
				printValue(s_v, type, C, string_out);
				string_out.flush();
				symbolic_value = SVal();
			}
		}
	public:
		/*
		 * t: type
		 * s_v: the symbol that may contain the value
		 * C: the context for printing the value, if it is known
		 * alive: is the symbol still alive?
		 */
		CurrentSymbolValue(enum s_type t, SVal s_v,
				   CheckerContext &C, bool alive) :
		creation_time(clock()), type(t), concrete_value()
		{
			initValue(s_v, C, alive);
		}

		/*
		 * Get type.
		 * returns type
		 */
		enum s_type getReturnType() const
		{
			return type;
		}

		/*
		 * Get symbolic_value
		 * returns symbolic_value
		 */
		SVal getSymbolicValue() const
		{
			return symbolic_value;
		}

		/*
		 * Get known.
		 * returns known
		 */
		bool isKnown()
		{
			return known;
		}

		/*
		 * Print the value.
		 * out: the output stream to print to
		 * C: the context for generating the string to print
		 */
		void print(llvm::raw_ostream &out, CheckerContext &C) const
		{
			if (known) {
				out << concrete_value;
			} else {
				printValue(symbolic_value, type, C, out);
			}
		}

		bool operator==(const CurrentSymbolValue &X) const
		{
			return (X.creation_time == creation_time) &&
			       (X.type == type) && (X.known == known);
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddInteger(creation_time);
			ID.AddInteger(type);
			ID.AddBoolean(known);
		}
	};

	/* information about a function's return value */
	struct ReturnSite {
	private:
		/*
		 * the creation time of this struct,
		 * to keep it unique in the state
		 */
		clock_t creation_time;
		std::string callee; /* the callee that returned */
		std::string location; /* the call site */
		unsigned depth; /* the stack depth of the call */
		unsigned n_calls; /* the segment length up to this call */
		/* Is the return value already exactly known? */
		bool fixed;
		/* If so, print out its representation. */
		std::string fixed_value;
		/* If not, we will need to retrieve it from the symbol later. */
		SVal value;
	public:
		/*
		 * ce: callee
		 * loc: location
		 * d: depth
		 * n_c: n_calls
		 * val: contains value
		 * C: the context for printing the value, if it is known
		 */
		ReturnSite(std::string ce, std::string loc, unsigned d,
			   unsigned n_c, CurrentSymbolValue &val,
			   CheckerContext &C) :
		creation_time(clock()), callee(ce), location(loc), depth(d),
		n_calls(n_c), fixed_value(), value(val.getSymbolicValue())
		{
			if ((fixed = val.isKnown())) {
				llvm::raw_string_ostream
				fixed_stream(fixed_value);

				val.print(fixed_stream, C);
				fixed_stream.flush();
			}
		}

		/*
		 * Get depth.
		 * returns depth
		 */
		unsigned getDepth() const
		{
			return depth;
		}

		/*
		 * Get n_calls.
		 * returns n_calls
		 */
		unsigned getNCalls() const
		{
			return n_calls;
		}

		/*
		 * Get the SymbolRef of value.
		 * returns the SymbolRef of value
		 */
		SymbolRef getValueRef() const
		{
			return value.getAsSymbol();
		}

		bool operator==(const ReturnSite &X) const
		{
			return (X.creation_time == creation_time) &&
			       (X.callee == callee) &&
			       (X.location == location) &&
			       (X.depth == depth) &&
			       (X.n_calls == n_calls) && (X.fixed == fixed) &&
			       (X.fixed_value == fixed_value);
		}

/* marks part of segment after the location, and before the return value */
#define PRE_RET_VAL	";"
/* marks the part of the segment before the length */
#define PRE_FUNC_COUNT	"#"
/* marks segments of the path */
#define PATH_DELIM	"@"
		void print(llvm::raw_ostream &out, unsigned offset, bool first,
			   const CurrentSymbolValue *ret_val,
			   CheckerContext &C) const
		{
			if (!first) {
				out << PRE_FUNC_COUNT << (n_calls - offset) <<
					PATH_DELIM;
			}
			out << callee << " " << location << PRE_RET_VAL;

			if (fixed) {
				out << fixed_value;
			} else {
				ret_val->print(out, C);
			}
		}

		void Profile(llvm::FoldingSetNodeID &ID) const
		{
			ID.AddInteger(creation_time);
			ID.AddString(callee);
			ID.AddString(location);
			ID.AddInteger(depth);
			ID.AddInteger(n_calls);
			ID.AddBoolean(fixed);
			ID.AddString(fixed_value);
		}
	};
	/* the APEx checker for gathering path information */
	class CHECKER_NAME : public Checker<check::PostCall, check::PreCall,
					    check::PreStmt<ReturnStmt>,
#ifdef CHECK_STMT
					    check::PreStmt<Stmt>,
#endif
					    check::DeadSymbols,
					    check::EndFunction> {
	private:
		/*
		 * set of functions
		 * for which we want to find error specifications
		 */
		mutable std::map<std::string, int> func_hash;
		/* set of exit functions */
		mutable std::map<std::string, int> exit_hash;
		/*
		 * Parse the configuration file
		 * to populate func_hash and exit_hash.
		 */
		void parseConfig();
		/*
		 * Do we want to track this function?
		 * callee: the function name
		 * type: if not NULL, will store the type of the function
		 * Call: the call event, which contains function metadata
		 */
		bool careFunction(StringRef &callee, enum s_type *type,
				  const CallEvent &Call) const;
		/*
		 * Get the depth of the call stack during
		 * the current point in the path exploration.
		 * C: the context containing the call stack information.
		 * returns the current depth of the stack
		 */
		unsigned getStackDepth(CheckerContext &C) const;
		/*
		 * Find the location of the call site.
		 * Call: the call event
		 * C: the context for printing the call site
		 * returns the string representation of the call site
		 */
		std::string getLocFromCall(const CallEvent &Call,
					   CheckerContext &C) const;
		/*
		 * Redirect the output stream to a random file.
		 */
		void randomizeOut();
		/*
		 * If the value is a symbol,
		 * increment a reference to it in the state.
		 * If the symbol has not been referenced before,
		 * store its symbol.
		 * val: the symbol that may need a reference
		 * old_state: the old state that keeps track of the references
		 * returns the state, updated with a new reference, or unchanged
		 */
		ProgramStateRef maybeGetValue(CurrentSymbolValue *val,
					      ProgramStateRef old_state) const;
		/*
		 * Decrement a reference to the value.
		 * If it has reached 0, remove the reference completely.
		 * val_ref: the value reference, which is assumed
		 *	    to have at least one reference
		 * old_state: the old state that keeps track of the references
		 * returns the updated state
		 */
		ProgramStateRef putValue(SymbolRef val_ref,
					 ProgramStateRef old_state) const;
		/*
		 * Initialize the state of the caller, if it has not been,
		 * already.
		 * C: the context of the caller
		 * old_state: the current state
		 * n_calls: the call count so far
		 * returns the new state,
		 * or NULL if the caller state has been initialized
		 */
		ProgramStateRef
		handleCallerStart(CheckerContext &C, ProgramStateRef old_state,
				  unsigned n_calls) const;
		/*
		 * Wrap handleCallerStart
		 * and automatically find the n_calls parameter.
		 * C: the context of the caller
		 * old_state: the current state
		 * returns the new state,
		 * or NULL if the caller state has been initialized
		 */
		ProgramStateRef
		handleCallerStart(CheckerContext &C,
				  ProgramStateRef old_state) const;
		/*
		 * Print and clear the caller's stack entry.
		 * ret_str: the string representation
		 *	    of the caller's return value
		 * C: the current context
		 * loc: the location of the end of the function
		 * old_state: the old state
		 * exit: did the function end by terminating the program?
		 * returns the new state if it changed, NULL otherwise
		 */
		ProgramStateRef
		handleCallerEnd(std::string ret_str,
				CheckerContext &C, std::string loc,
				ProgramStateRef old_state, bool exit) const;
		/*
		 * Wrap handleCallerEnd, and generate the ret_str parameter
		 * using the return value and its type.
		 * ret: the return value of the caller
		 * retType: the return type object
		 * C: the current context
		 * loc: the location of the end of the function
		 * old_state: the old state
		 * exit: did the function end by terminating the program?
		 * returns the new state if it changed, NULL otherwise
		 */
		ProgramStateRef
		handleCallerEnd(SVal ret, QualType retType,
				CheckerContext &C, std::string loc,
				ProgramStateRef old_state, bool exit) const;
		/*
		 * Check if the function is an exit function.
		 * function_name: the function to check if it is an exit
		 * returns true iff the function is in the set of exit functions
		 */
		bool isExit(llvm::StringRef &function_name) const;
		/*
		 * Check for exit functions at the end of the caller.
		 * Call: the potential exit call
		 * C: the current context for printing path information
		 * old_state: the old state
		 * callee: the name of the potential exit function
		 * loc: the call site of the potential exit function
		 * returns the new state if it changed, NULL otherwise
		 */
		ProgramStateRef
		checkExit(const CallEvent &Call, CheckerContext &C,
			  ProgramStateRef old_state, StringRef callee,
			  std::string loc) const;
		/*
		 * Check if the callee needs to be counted in the stack.
		 * Call: information about the call
		 * C: the current context for printing path information
		 * old_state: the old state
		 * stack_depth: the current depth of the call stack
		 * callee: the name of the callee
		 * loc: the call site
		 * returns the new state if it changed, NULL otherwise
		 */
		ProgramStateRef
		checkCallee(const CallEvent &Call, CheckerContext &C,
			    ProgramStateRef old_state, unsigned stack_depth,
			    StringRef callee, std::string loc) const;
	public:
		CHECKER_NAME();
		/*
		 * Print a line that is formatted for an analyzer to read.
		 * str: the message body
		 * out: the output stream to print to
		 * preamble: the preamble of the line to print,
		 *	     which tells the analyzer if it should be read
		 */
		void printMsg(std::string str, raw_ostream &out,
			      std::string preamble) const;
		/*
		 * Record return value information.
		 * Call: information about the returned call
		 * C: the current context for printing path information,
		 *    and fetching and setting the state
		 */
		void checkPostCall(const CallEvent &Call,
				   CheckerContext &C) const;
		/*
		 * Check if the called function is an exit function,
		 * or needs to be put counted in the stack.
		 * If counting function calls, also count it here.
		 * Call: information about the returned call
		 * C: the current context for printing path information,
		 *    and fetching and setting the state
		 */
		void checkPreCall(const CallEvent &Call,
				  CheckerContext &C) const;
		/*
		 * Gather unknown return values that have died,
		 * since this is the last place where they can be changed.
		 * SymReaper: contains the dead symbols
		 * C: the current context, containing the state
		 */
		void checkDeadSymbols(SymbolReaper &SymReaper,
				      CheckerContext &C) const;
#ifdef CHECK_STMT
		/*
		 * Count the statement.
		 * S: the statement to count
		 * C: the current context, containing the state
		 */
		void checkPreStmt(const Stmt *S, CheckerContext &C) const;
#endif
		/*
		 * Handle the end of a function due to a return.
		 * S: the return statement containing the return value
		 * C: the current context for printing path information,
		 *    and fetching and setting the state
		 */
		void checkPreStmt(const ReturnStmt *S, CheckerContext &C) const;
		/*
		 * Clean out the caller's state.
		 * C: the current context, containing the state
		 */
		void checkEndFunction(CheckerContext &C) const;
	};
} /* end anonymous namespace */

/* the identifying suffix of the randomly-named output file */
#define LOG_SUFFIX ".ae.log"
/* the length of the output file's suffix */
#define LOG_SUFFIX_LEN (strlen(LOG_SUFFIX) + 1)

#include <fcntl.h>
#include <stdlib.h>
#include <time.h>
#include <inttypes.h>
#include <unistd.h>
/* the buffer length for the file name */
#define FNAME_SIZE	(33 + LOG_SUFFIX_LEN)
/* the randomness source */
#define URANDOM_PATH	"/dev/urandom"

unsigned CHECKER_NAME::getStackDepth(CheckerContext &C) const
{
	unsigned stack_depth = 0;

	for (const LocationContext *LCtx = C.getLocationContext(); LCtx;
			LCtx = LCtx->getParent()) {
		if (LCtx->getKind()==LocationContext::ContextKind::StackFrame) {
			stack_depth++;
		}
	}

	return stack_depth;
}

std::string
CHECKER_NAME::getLocFromCall(const CallEvent &Call, CheckerContext &C) const
{
	std::string loc;
	const Expr *origin_expr = Call.getOriginExpr();

	if (origin_expr) {
		loc = origin_expr->getExprLoc()
				 .printToString(C.getSourceManager());
	} else {
		loc = "";
	}

	return loc;
}

/* counts the number of entries on each stack layer */
REGISTER_MAP_WITH_PROGRAMSTATE(StackRows, StackKey, StackRow)

/* keeps track of the return values */
REGISTER_MAP_WITH_PROGRAMSTATE(ReturnSites, StackRowKey, ReturnSite)

/*
 * keeps track of the path length,
 * which might be either number of functions or number of statements
 */
REGISTER_MAP_WITH_PROGRAMSTATE(NCallsStack, StackKey, NCalls)
/* lookup table for current value of a return symbol */
REGISTER_MAP_WITH_PROGRAMSTATE(SymbolValues, SymbolRef, CurrentSymbolValue)
/*
 * reference counter that keeps track of whether or not
 * a symbol should be kept in SymbolValues
 */
REGISTER_MAP_WITH_PROGRAMSTATE(SymbolValuesCounter, SymbolRef, unsigned)
/* the path length in the current caller */
REGISTER_TRAIT_WITH_PROGRAMSTATE(TopNCalls, unsigned)
/* Has the checker started counting the path length in the current caller? */
REGISTER_TRAIT_WITH_PROGRAMSTATE(StartedCaller, unsigned)

/* keeps track of whether each layer has started or been printed */
REGISTER_MAP_WITH_PROGRAMSTATE(SimpleStack, StackKey, SimpleStatus)

void CHECKER_NAME::randomizeOut()
{
	char fname[FNAME_SIZE];
	int random_file = open(URANDOM_PATH, O_RDONLY);
	unsigned random_bytes;

	if (random_file >= 0) {
		read(random_file, &random_bytes, sizeof(random_bytes));
		close(random_file);
	} else {
		srandom(time(NULL));
		random_bytes = random() % INT_MAX;
	}

	snprintf(fname, FNAME_SIZE, "%08x_%016lx" LOG_SUFFIX, random_bytes,
			time(NULL));

	freopen(fname, "w", stderr);
}

ProgramStateRef
CHECKER_NAME::maybeGetValue(CurrentSymbolValue *val,
			    ProgramStateRef old_state) const
{
	if (val->isKnown()) {
		/*
		 * If the value is known,
		 * we don't need to keep track of the symbol.
		 */
		return old_state;
	} else {
		/*
		 * The value is unknown, so we still have to use the symbol.
		 */
		SymbolRef val_ref = val->getSymbolicValue().getAsSymbol();
		ProgramStateRef state = old_state;
		const unsigned *
		old_count = state->get<SymbolValuesCounter>(val_ref);

		if (old_count == NULL) {
			/* The first time, we also need to store the symbol. */
			state = state->set<SymbolValuesCounter>(val_ref, 1);
			state = state->set<SymbolValues>(val_ref, *val);
		} else {
			/* Other times, we only increment the count */
			state = state->set<SymbolValuesCounter>(val_ref,
					*old_count + 1);
		}

		return state;
	}
}

ProgramStateRef
CHECKER_NAME::putValue(SymbolRef val_ref, ProgramStateRef old_state) const
{
	ProgramStateRef state = old_state;
	const unsigned *old_count = state->get<SymbolValuesCounter>(val_ref);
	unsigned new_count = *old_count - 1;

	if (new_count == 0) {
		/* The value is no longer used at all. */
		state = state->remove<SymbolValuesCounter>(val_ref);
		state = state->remove<SymbolValues>(val_ref);
	} else {
		/* Only decrement the counter. */
		state = state->set<SymbolValuesCounter>(val_ref, new_count);
	}

	return state;
}

ProgramStateRef
CHECKER_NAME::handleCallerStart(CheckerContext &C, ProgramStateRef old_state,
				unsigned n_calls) const
{
	ProgramStateRef state = old_state;
	unsigned stack_depth = getStackDepth(C);
	StackKey stack_key(stack_depth);

	/* The caller's state has already been initialized. */
	if (state->get<StartedCaller>()) {
		return NULL;
	}

	/*
	 * Initialize the caller's state
	 * by keeping track of the beginning length.
	 */
	state = state->set<NCallsStack>(stack_key,
					NCalls(n_calls, stack_depth));

	state = state->set<StartedCaller>(1);

	return state;
}

ProgramStateRef
CHECKER_NAME::handleCallerStart(CheckerContext &C,
				ProgramStateRef old_state) const
{
	unsigned n_calls = old_state->get<TopNCalls>();
	return handleCallerStart(C, old_state, n_calls);
}

#define POSTCONDITION_PREAMBLE "AutoEPEx"

#define EXIT_MARKER "$"

ProgramStateRef
CHECKER_NAME::handleCallerEnd(std::string ret_str, CheckerContext &C,
			      std::string loc, ProgramStateRef old_state,
			      bool exit) const
{
	ProgramStateRef state = old_state == NULL ? C.getState() : old_state;
	unsigned stack_depth = getStackDepth(C);
	StackKey stack_key(stack_depth);
	const StackRow *row = state->get<StackRows>(stack_key);
	const NCalls *n_calls_struct = state->get<NCallsStack>(stack_key);
	const clang::Decl *DC = C.getCurrentAnalysisDeclContext()->getDecl();
	const SimpleStatus *simple_status;
	bool changed_fsc = false;
	unsigned site_i, n_sites;
	unsigned last_n_calls, base;
	std::string ret_out;
	llvm::raw_string_ostream ret_out_stream(ret_out);
	std::string args_out;
	llvm::raw_string_ostream args_out_stream(args_out);
	std::string caller;

	caller = DC->getAsFunction()->getNameInfo().getAsString();

	last_n_calls = state->get<TopNCalls>();

	/*
	 * Record that the caller will be printed,
	 * if the caller has been initialized and has not been printed.
	 */
	simple_status = state->get<SimpleStack>(stack_key);
	if (simple_status != NULL && !simple_status->isPrinted() &&
	    simple_status->isSeen()) {
	    	state = state->set<SimpleStack>(stack_key,
						SimpleStatus(true, true,
							     stack_depth));
		changed_fsc = true;
	}

	/*
	 * Exit if the row has not been recorded,
	 * or it has already been printed.
	 */
	if (row && !row->isPrinted()) {
		n_sites = row->getNEntries();
	} else {
		if (changed_fsc) {
			return state;
		}
		return NULL;
	}

	/* Get the path length. */
	if (n_calls_struct) {
		base = n_calls_struct->getNCalls();
	} else if (stack_depth == 1) {
		base = 0;
	} else {
		if (changed_fsc) {
			return state;
		}
		return NULL;
	}

	/* Print the return values of the interesting callees. */
	for (site_i = 0; site_i < n_sites; site_i++) {
		StackRowKey stack_row_key(stack_depth, site_i);
		const ReturnSite *site = state->get<ReturnSites>(stack_row_key);
		const CurrentSymbolValue
		*val = state->get<SymbolValues>(site->getValueRef());
		bool is_first = site_i == 0;

		site->print(ret_out_stream, base, is_first, val, C);
		state = state->remove<ReturnSites>(stack_row_key);
		base = site->getNCalls();
		if (val) {
			state = putValue(site->getValueRef(), state);
		}
	}

	/* Record that the caller has been printed. */
	state = state->set<StackRows>(stack_key, StackRow(0, true));

	/* Print the return information at the end of the function. */
	caller = DC->getAsFunction()->getNameInfo().getAsString();
	ret_out_stream << PRE_FUNC_COUNT << (last_n_calls - base) <<
			  PATH_DELIM;
	ret_out_stream << caller + " " + loc << ";";
	ret_out_stream << ret_str;
	if (exit) {
		ret_out_stream << EXIT_MARKER;
	}

	printMsg(ret_out_stream.str(), OUT_STREAM, POSTCONDITION_PREAMBLE);

	return state;
}

ProgramStateRef
CHECKER_NAME::handleCallerEnd(SVal ret, QualType type_struct,
			      CheckerContext &C, std::string loc,
			      ProgramStateRef old_state, bool exit) const
{
	enum s_type ret_type = getType(type_struct);	
	std::string ret_str;

	/* Generate the string representation of the return value. */
	if (ret_type == N_TYPES) {
		ret_str = VOID_TYPE;
	} else {
		llvm::raw_string_ostream ret_stream(ret_str);
		printValue(ret, ret_type, C, ret_stream);
		ret_stream.flush();
	}

	return handleCallerEnd(ret_str, C, loc, old_state, exit);
}

bool CHECKER_NAME::isExit(llvm::StringRef &function_name) const
{
	return exit_hash.find(function_name) != exit_hash.end();
}

/* abort does not have a parameter, although it is always considered an error */
#define DUMMY_VAR "abort_return"
/* the assumed type of abort, so that it is treated as an error */
#define DUMMY_TYPE "I"
/* the assumed type of parameter, so that it is treated as an error */
#define DUMMY_VAL "-1"

ProgramStateRef
CHECKER_NAME::checkExit(const CallEvent &Call, CheckerContext &C,
			ProgramStateRef old_state, StringRef callee,
			std::string loc) const
{
	ProgramStateRef state = old_state == NULL ? C.getState() : old_state;

	if (isExit(callee)) {
		unsigned int n_args = Call.getNumArgs();
		ProgramStateRef end_state;
		CallEvent::param_type_iterator TyI = Call.param_type_begin();
		/* If there is no parameter, assume an error exit. */
		if (n_args == 0) {
			end_state = handleCallerEnd(DUMMY_TYPE SYMBOL_PRE
						    DUMMY_VAR ASSIGN
						    DUMMY_VAL,
						    C, loc, state, true);
		} else {
			end_state = handleCallerEnd(Call.getArgSVal(0), *TyI,
						    C, loc, state, true);
		}
		if (end_state != NULL) {
			state = end_state;
		}
	}
	return state;
}

ProgramStateRef
CHECKER_NAME::checkCallee(const CallEvent &Call, CheckerContext &C,
			  ProgramStateRef old_state, unsigned stack_depth,
			  StringRef callee, std::string loc) const
{
	StackKey stack_key(stack_depth);
	ProgramStateRef state = old_state == NULL ? C.getState() : old_state;

	/* If we care about the function, count it in the stack. */
	if (careFunction(callee, NULL, Call)) {
		const StackRow *old_row = state->get<StackRows>(stack_key);
		if (old_row == NULL || !old_row->isPrinted()) {
			unsigned end = old_row == NULL ?
				       0 : old_row->getNEntries();
			StackRowKey append_key(stack_depth, end);
			std::string loc= getLocFromCall(Call, C);

			state = state->set<StackRows>(stack_key,
						      StackRow(end + 1,
							       false));
			return state;
		} else {
			return NULL;
		}
	}
	return NULL;
}

/* the name of the configuration file */
#define CONFIG_FILE "analyze_func_list.txt"
/* the maximum allowed entry length in the configuration file */
#define CONFIG_LINE_MAX 2048

#define EXIT_FUNC_MARKER '0'

void CHECKER_NAME::parseConfig()
{
	FILE *fp = fopen(CONFIG_FILE, "r");
	char buf[CONFIG_LINE_MAX];
	char path[PATH_MAX];

	if (fp != NULL) {
		while (fgets(buf, sizeof(buf), fp) != NULL) {
			size_t len = strlen(buf);

			if (len > 0) {
				size_t last_i = len - 1;

				if (buf[last_i]== '\n') {
					buf[last_i] = '\0';
					len = last_i;
				}

				/* The line is not empty. */
				if (len > 0)
				{
					/* The line has an exit function. */
					if (buf[0] == EXIT_FUNC_MARKER) {
						if (len > 1) {
							exit_hash[buf + 1] = 1;
						}
					/* The line is an analyzed function. */
					} else {
						func_hash[buf] = 1;
					}
				}
			}
		}

		fclose(fp);
		OUT_STREAM << "Success:\n";
		OUT_STREAM << func_hash.size() << " normal functions added\n";
		OUT_STREAM << exit_hash.size() << " exit functions added\n";
	} else {
		OUT_STREAM << "Failed to load " <<
			      std::string(getcwd(path, sizeof(path))) << "/" <<
			      CONFIG_FILE << "\n";
	}
	OUT_STREAM << "\n";
}

bool CHECKER_NAME::careFunction(StringRef &callee, enum s_type *type,
				const CallEvent &Call) const
{
	QualType type_struct = Call.getResultType();	
	enum s_type tmp_type = getType(type_struct);

	if (type != NULL) {
		*type = tmp_type;
	}

	return ((func_hash.size() == 0) ||
	        (func_hash.find(callee) != func_hash.end())) &&
	       (tmp_type != N_TYPES);
}

#define NEW_FILE_MARKER	"NEW FILE\n"

CHECKER_NAME::CHECKER_NAME()
{
	parseConfig();
	randomizeOut();
	printMsg(NEW_FILE_MARKER, OUT_STREAM, POSTCONDITION_PREAMBLE);
}

void
CHECKER_NAME::checkPostCall(const CallEvent &Call, CheckerContext &C) const
{
	SVal ret_val = Call.getReturnValue();
	const IdentifierInfo *callee_id = Call.getCalleeIdentifier();
	unsigned stack_depth = getStackDepth(C);
	ProgramStateRef state = C.getState();
	bool changed = false;
	enum s_type ret_type;
	StringRef callee_name;

	if (!callee_id) {
		return;
	}
	callee_name = callee_id->getName();

	/*
	 * Since we have already entered a call statement,
	 * we know that there is something to count.
	 */
	if (!state->get<StartedCaller>()) {
		state = state->set<StartedCaller>(1);
		changed = true;
	}

	/*
	 * If we care about the function,
	 * and the path in the caller has not been printed,
	 * record its return value.
	 */
	if (careFunction(callee_name, &ret_type, Call)) {
		StackKey stack_key(stack_depth);
		const StackRow *old_row = state->get<StackRows>(stack_key);
		const SimpleStatus *simple_status;
		if (!old_row->isPrinted()) {
			unsigned last = old_row->getNEntries() - 1;
			StackRowKey append_key(stack_depth, last);
			std::string loc= getLocFromCall(Call, C);
			CurrentSymbolValue val(ret_type, ret_val, C, true);
			unsigned n_calls = state->get<TopNCalls>();

			state = state->set<ReturnSites>(append_key,
							ReturnSite(callee_name,
								   loc,
								   stack_depth,
								   n_calls,
								   val, C));
			state = maybeGetValue(&val, state);
			changed = true;
		}
		simple_status = state->get<SimpleStack>(stack_key);
		if (simple_status == NULL || (!simple_status->isPrinted() &&
					      !simple_status->isSeen())) {
			state =
			state->set<SimpleStack>(stack_key,
						SimpleStatus(false, true,
							     stack_depth));
			changed = true;
		}
	}

	if (changed) {
		C.addTransition(state);
	}
}


void CHECKER_NAME::checkDeadSymbols(SymbolReaper &SymReaper,
				    CheckerContext &C) const
{
	ProgramStateRef state = C.getState();
	bool changed = false;

	/*
	 * Look for dead return symbols that will need to have their values set.
	 */
	for (SymbolReaper::dead_iterator dead_i = SymReaper.dead_begin(),
	     dead_end = SymReaper.dead_end(); dead_i != dead_end; ++dead_i) {
		SymbolRef sym = *dead_i;
		const CurrentSymbolValue *
		old_value = state->get<SymbolValues>(sym);

		if (old_value) {
			enum s_type type = old_value->getReturnType();
			SVal value = old_value->getSymbolicValue();

			state =
			state->set<SymbolValues>(sym,
						 CurrentSymbolValue(type, value,
								    C, false));
			changed = true;
		}
	}
	if (changed) {
		C.addTransition(state);
	}
}

void CHECKER_NAME::checkPreCall(const CallEvent &Call, CheckerContext &C) const
{
	ProgramStateRef state = C.getState();
	const IdentifierInfo *callee_info = Call.getCalleeIdentifier();
	std::string loc;
	unsigned stack_depth = getStackDepth(C);
	StringRef callee;
	ProgramStateRef running_state;
	unsigned n_calls;
#ifndef CHECK_STMT
	unsigned new_n_calls;
#endif

	if (!callee_info) {
		return;
	}
	callee = callee_info->getName();

	/* Get the location and path length at the call. */
	loc = getLocFromCall(Call, C);
	n_calls = state->get<TopNCalls>();
#ifndef CHECK_STMT
	/*
	 * Count the function, if that's the checker's measure for path length.
	 */
	new_n_calls = n_calls + 1;
	state = state->set<TopNCalls>(new_n_calls);
#endif
	if ((running_state = handleCallerStart(C, state, n_calls)) != NULL) {
		state = running_state;
	}
	if ((running_state = checkExit(Call, C, state, callee, loc)) != NULL) {
		state = running_state;
	}
	if ((running_state = checkCallee(Call, C, state, stack_depth,
					 callee, loc)) != NULL) {
		state = running_state;
	}

	/* We have not yet counted anything in the body of the callee. */
	state = state->set<StartedCaller>(0);
	C.addTransition(state);
}

void
CHECKER_NAME::checkPreStmt(const ReturnStmt *S, CheckerContext &C) const
{
	const Expr *ret_expr = S->getRetValue();
	ProgramStateRef tmp_state;
	const clang::Decl
	*DC = C.getCurrentAnalysisDeclContext()->getDecl();
	std::string loc;

	if (ret_expr) {
		/* There is a return symbol to print. */
		loc = ret_expr->getExprLoc()
			      .printToString(C.getSourceManager());
		SVal ret_val;
		QualType ret_type;

		ret_val = C.getState()->getSVal(ret_expr,
						C.getLocationContext());
		ret_type = DC->getAsFunction()->getReturnType();

		tmp_state = handleCallerEnd(ret_val, ret_type, C, loc, NULL,
					    false); 
	} else {
		/* Just mark the return value as void. */
		loc = S->getReturnLoc()
		       .printToString(C.getSourceManager());
		tmp_state = handleCallerEnd(VOID_TYPE, C, loc, NULL, false); 
	}

	if (tmp_state != NULL) {
		C.addTransition(tmp_state);
	}
}

/* If the function ends without an actual return site, use this dummy value. */
#define END_LOC	"function_end:0:0"

void CHECKER_NAME::checkEndFunction(CheckerContext &C) const
{
	unsigned stack_depth = getStackDepth(C);
	StackKey stack_key(stack_depth);
	ProgramStateRef state = C.getState();
	const NCalls *n_calls_struct = state->get<NCallsStack>(stack_key);
	bool changed = false;
	ProgramStateRef print_state;

	/* Print the path, if it has not already been. */
	print_state = handleCallerEnd(VOID_TYPE, C, END_LOC, state, false);
	if (print_state != NULL) {
		state = print_state;
		changed = true;
	}

	/* Clean up any state for the current layer. */
	if (n_calls_struct != NULL) {
		unsigned n_calls = n_calls_struct->getNCalls();
		state = state->remove<NCallsStack>(stack_key);
		state = state->set<TopNCalls>(n_calls);
		changed = true;
	}

	if (state->get<StackRows>(stack_key) != NULL) {
		state = state->remove<StackRows>(stack_key);
		changed = true;
	}

	if (state->get<SimpleStack>(stack_key) != NULL) {
		state = state->remove<SimpleStack>(stack_key);
		changed = true;
	}

	if (changed) {
		C.addTransition(state);
	}
}

/* delimits the preamble and body of the message */
#define POST_PREAMBLE	": "

void CHECKER_NAME::printMsg(std::string str, raw_ostream &out,
			    std::string preamble) const
{
	out << preamble << POST_PREAMBLE << str << "\n";
}

#endif /* APEX_H */
