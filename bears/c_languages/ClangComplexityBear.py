from clang.cindex import Index, CursorKind

from coalib.bears.LocalBear import LocalBear
from coalib.results.Result import Result
from coalib.results.SourceRange import SourceRange
from bears.c_languages.ClangBear import clang_available


class ClangComplexityBear(LocalBear):
    """
    Calculates cyclomatic complexity of each function and displays it to the
    user.
    """
    check_prerequisites = classmethod(clang_available)
    decisive_cursor_kinds = {
        CursorKind.IF_STMT, CursorKind.WHILE_STMT, CursorKind.FOR_STMT,
        CursorKind.DEFAULT_STMT, CursorKind.CASE_STMT}

    def function_key_points(self, cursor, top_function_level=False):
        """
        Calculates number of function's decision points and exit points.

        :param top_function_level: Whether cursor is in the top level of
                                   the function.
        """
        decisions, exits = 0, 0

        for child in cursor.get_children():
            if child.kind in self.decisive_cursor_kinds:
                decisions += 1
            elif child.kind == CursorKind.RETURN_STMT:
                exits += 1
                if top_function_level:
                    # There is no point to move forward, so just return.
                    return decisions, exits
            child_decisions, child_exits = self.function_key_points(child)
            decisions += child_decisions
            exits += child_exits

        if top_function_level:
            # Implicit return statement.
            exits += 1

        return decisions, exits

    def complexities(self, cursor, filename):
        """
        Calculates cyclomatic complexities of functions.
        """

        file = cursor.location.file

        if file is not None and file.name != filename:
            # There is nothing to do in another file.
            return

        if cursor.kind == CursorKind.FUNCTION_DECL:
            child = next((child for child in cursor.get_children()
                          if child.kind != CursorKind.PARM_DECL),
                         None)
            if child:
                decisions, exits = self.function_key_points(child, True)
                complexity = max(1, decisions - exits + 2)
                yield cursor, complexity
        else:
            for child in cursor.get_children():
                yield from self.complexities(child, filename)

    def run(self, filename, file, max_complexity: int=8):
        """
        Calculates cyclomatic complexity of functions in file.

        :param max_complexity:  Maximum cyclomatic complexity that is
                                considered to be normal. The value of 10 had
                                received substantial corroborating evidence.
                                But the general recommendation: "For each
                                module, either limit cyclomatic complexity to
                                [the agreed-upon limit] or provide a written
                                explanation of why the limit was exceeded."
        """

        root = Index.create().parse(filename).cursor
        for cursor, complexity in self.complexities(root, filename):
            if complexity > max_complexity:
                affected_code = (SourceRange.from_clang_range(cursor.extent),)
                yield Result(
                    self,
                    "The cyclomatic complexity of function {function} is "
                    "{complexity} which exceeded maximal recommended value "
                    "of {rec_value}.".format(
                        function=cursor.displayname,
                        complexity=complexity,
                        rec_value=max_complexity),
                    affected_code=affected_code)