#APEx: Automated Tool for Generating Error Specifications

##What is APEx?

APEx is a tool that automatically generates error specifications
for C API functions by analyzing its usage.
The details of the method are described in
[APEx: Automated Inference of Error Specifications for C APIs](https://yujokang.github.io/papers/apex_2016.pdf),
by [Yuan Kang](https://yujokang.github.io/),
[Baishakhi Ray](http://rayb.info/) and
[Suman Jana](http://sumanj.info/),
presented at the 2016 International Conference on
Automated Software Engineering (ASE 2016).

##Why is APEx useful?
Enforcing correct error handling in C is difficult for programmers,
as well as automated checking tools.
Since C has no built-in error reporting mechanism,
developers rely on custom methods,
usually using error codes passed through return values,
to report errors upstream.
Knowing these error codes, or error specifications,
is important both for the developer to check and handle errors correctly,
and for any bug finding tools to know what to check.
Tools such as [EPEx](https://github.com/yujokang/EPEx)
rely on error specifications to narrow down error conditions.
However, manually discovering error specifications, is a tedious task,
and for fully automating the discovery of error handling bugs,
we wish to also generate these specifications automatically.

We used APEx to infer error specifications
for Libgcrypt, GnuTLS, GTK, libc, OpenSSL and zlib,
and used the specifications to find error handling bugs
in applications that use these libraries.

##How does APEx work?
APEx leverages the fact that error-handling code is more simple
than regular code,
and the availability of multiple applications using each library.
Since error-handling code has less valid data to process,
the execution contains less statements and less branches,
which also means that there are less paths that follow
the failure of a function.

To eliminate noise due to exceptions in this heuristic,
as well as programming errors,
APEx has each application vote on the likely error specification
of each API function,
and chooses the specification with a significant plurality.

#Installation and usage

##Prerequisites
###CMake:
If you are using Ubuntu, you might need a newer version of CMake
than what you can get through apt-get.
You can download the source at:
https://cmake.org/download/
It can be built and installed using the standard
`./configure; make; sudo make install`

##LLVM and clang:
You can build the necessary parts of LLVM and clang at:
http://clang.llvm.org/get_started.html
It is not necessary to follow the optional steps 4-6.
To keep clang in your path, add the following line to `~/.bashrc`:
`export PATH=[build directory]bin:$PATH`
The rest of the instructions assume that you have not done this,
and will refer to `[build directory]bin/` as the `binary directory`.
If you did add the binary directory to your path,
you don't have to enter the binary directory in your commands.
To analyze a single file, however, you still have to enter the build directory
that contains the include folder.

##Installing the Clang checker:
1. Go to the directory
`[path to llvm source folder]tools/clang/lib/StaticAnalyzer/Checkers`
2. Add the source files:
Enter `ln -s [path to this release folder]checker/APEx.h .`,
`ln -s [path to this release folder]checker/APExFunc.cpp .`, and
`ln -s [path to this release folder]checker/APExStmt.cpp .`.
3. Register the `alpha.unix.APExFuncChecker` and
`alpha.unix.APExStmtChecker` checkers:
Open `../../../include/clang/StaticAnalyzer/Checkers/Checkers.td`, look for the block starting with
`let ParentPackage = UnixAlpha in {`,
and inside it, add the text:
```
def APExFuncChecker : Checker<"APExFuncChecker">,
  HelpText<"APEx path information gatherer that counts function calls.">,
  DescFile<"APExFunc.cpp">;
def APExStmtChecker : Checker<"APExStmtChecker">,
  HelpText<"APEx path information gatherer that counts statements.">,
  DescFile<"APExStmt.cpp">;
```
4. Register the source file to be compiled:
Open CMakeLists.txt, look for the block starting with
`add_clang_library(`, and inside it,
add the lines `APExFunc.cpp` and `APExStmt.cpp`.
5. Open `../../../include/clang/StaticAnalyzer/Core/PathSensitive/ConstraintManager.h`, and look for the `print` function
  in the `ConstraintManager` class,
  and add an extra parameter, `SymbolRef Sym = NULL`, ie. replace
```
  virtual void print(ProgramStateRef state,
                     raw_ostream &Out,
                     const char* nl,
                     const char *sep) = 0;
```
with
```
  virtual void print(ProgramStateRef state,
                     raw_ostream &Out,
                     const char* nl,
                     const char *sep,
                     SymbolRef Sym = NULL) = 0;
```
6. Open `../Core/RangeConstraintManager.cpp`,
  and find the declaration of `print` in the `RangeConstraintManager` class,
  and add the `Sym` parameter again, ie.
  replace
```
  void print(ProgramStateRef St, raw_ostream &Out,
             const char* nl, const char *sep) override; 
```
with
```
  void print(ProgramStateRef St, raw_ostream &Out,
             const char* nl, const char *sep, SymbolRef Sym = NULL) override;
```
  Then find the definition of `RangeConstraintManager::print`,
  and replace the header with the following header and code:
```
void RangeConstraintManager::print(ProgramStateRef St, raw_ostream &Out,
				   const char* nl, const char *sep,
				   SymbolRef Sym) {
  if (Sym) {
    const RangeSet *RangesToPrint = St->get<ConstraintRange>(Sym);
    if (RangesToPrint) {
      RangesToPrint->print(Out);
    }
    return;
  }
```
7. Compile clang with the new checker:
  Inside the build directory, enter `make clang`.

##Creating the function List
A file called `analyze_func_list.txt` needs to be in the directory
in which you run the checker.
It contains error specifications for fallible functions,
as well as exit functions.

###Entries
1. Analyzed functions: `[function name]`
2. Exit functions: `0[function name]`

###Sample function lists
The sample list of analyzed functions are in `sample_lists`
####Libraries
The the error specifications for checking the internals of library code
are stored in the following files, which you can use directly:
* Libgcrypt: `analyze_func_list_gcrypt.txt`
* GnuTLS: `analyze_func_list_gnutls.txt`
* GTK: `analyze_func_list_gtk.txt`
* libc: `analyze_func_list_libc.txt`
* OpenSSL: `analyze_func_list_ssl.txt`
* zlib: `analyze_func_list_zlib.txt`
Concatenate it with the list of exit functions, `exit_functions`,
in the same folder to use for the checker.

###Usage:
####Setup
If you are running the checker on a programming project,
you need to make sure that the function list is present in every directory
in which the compiler will run.
To create a link of the list file in every directory in the project folder,
run `python utilities/setup.py [original list file] [project root path]`

####Running the checker
It is recommended that you use `APExStmtChecker`,
as the statement count is a better indicator of an error path
than function call count.
If you do wish to use function count,
replace `APExStmtChecker` with `APExFuncChecker` in the following directions:
1. A single file:
  a. Keep `analyze_func_list` in the current working directory
  b. Enter:
  ```
  [binary directory]clang -cc1 -w -analyze -analyzer-opt-analyze-headers -analyzer-checker=alpha.unix.APExStmtChecker -I/usr/include -I[build directory]lib/clang/[version]/include/ [source file]
  ```
  c. The output file will have the suffix `.ae.log`.
2. A whole project:
  a. For every step in the build process (eg. ./configure and make),
  prepend the command with:
  ```
  [binary directory]scan-build -enable-checker alpha.unix.APExStmtChecker -analyze-headers --use-analyzer [binary directory]clang
  ```
  b. Run `python utilities/output_gatherer.py [combined output file] [project root path]`

####Generating the error specification
Run `python analysis/run_analyses.py [output file] [per-program checker log files...]`.
The error specifications will be in the output files,
in lines prepended by `ErrorSpec:`.

####A simple application of the error specification
Run `python analysis/check_specs.py [bug output folder] [error specification file] [per-program checker log files...].`
The bug files are stored in the bug output folder. Their name will be the same as the corresponding log file, except with the `.bugs` extension, which replaces the extension of the original file name, if it exists.
