"""Utilities for analyzing GraphQL query AST and request handling."""

from graphql.language.ast import (
    FieldNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    SelectionSetNode,
)


def calculate_query_depth(selection_set, fragments=None, current_depth=0):
    """Calculate the maximum nesting depth of a GraphQL selection set.

    Args:
        selection_set: A GraphQL SelectionSetNode to walk.
        fragments: Dict of fragment name to FragmentDefinitionNode for resolving spreads.
        current_depth: The current recursion depth (used internally).

    Returns:
        int: The maximum depth found.
    """
    if not selection_set or not isinstance(selection_set, SelectionSetNode):
        return current_depth

    max_depth = current_depth
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            child_depth = calculate_query_depth(selection.selection_set, fragments, current_depth + 1)
            max_depth = max(max_depth, child_depth)
        elif isinstance(selection, InlineFragmentNode):
            child_depth = calculate_query_depth(selection.selection_set, fragments, current_depth)
            max_depth = max(max_depth, child_depth)
        elif isinstance(selection, FragmentSpreadNode) and fragments:
            fragment = fragments.get(selection.name.value)
            if fragment:
                child_depth = calculate_query_depth(fragment.selection_set, fragments, current_depth)
                max_depth = max(max_depth, child_depth)

    return max_depth


def calculate_query_complexity(selection_set, fragments=None):
    """Calculate the complexity of a GraphQL query by counting total fields.

    Args:
        selection_set: A GraphQL SelectionSetNode to walk.
        fragments: Dict of fragment name to FragmentDefinitionNode for resolving spreads.

    Returns:
        int: The total number of fields in the query.
    """
    if not selection_set or not isinstance(selection_set, SelectionSetNode):
        return 0

    count = 0
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            count += 1
            count += calculate_query_complexity(selection.selection_set, fragments)
        elif isinstance(selection, InlineFragmentNode):
            count += calculate_query_complexity(selection.selection_set, fragments)
        elif isinstance(selection, FragmentSpreadNode) and fragments:
            fragment = fragments.get(selection.name.value)
            if fragment:
                count += calculate_query_complexity(fragment.selection_set, fragments)

    return count


def stash_meta_on_request(request, attr_name, meta):
    """Stash metadata on the request and its underlying WSGIRequest.

    For DRF views, ``info.context`` is a DRF ``Request`` wrapping a
    ``WSGIRequest``.  The Django middleware sees the ``WSGIRequest``, so
    we stash on both to ensure the metadata is accessible regardless of
    which request object is used.

    Args:
        request: The request object (DRF Request or WSGIRequest).
        attr_name: The attribute name to set on the request.
        meta: The metadata dict to stash.
    """
    setattr(request, attr_name, meta)
    wsgi_request = getattr(request, "_request", None)
    if wsgi_request is not None:
        setattr(wsgi_request, attr_name, meta)
