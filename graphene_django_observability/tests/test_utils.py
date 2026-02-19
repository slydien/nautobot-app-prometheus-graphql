"""Tests for the GraphQL AST analysis utilities."""

from django.test import TestCase
from graphql import parse

from graphene_django_observability.utils import (
    calculate_query_complexity,
    calculate_query_depth,
)


class CalculateQueryDepthTest(TestCase):
    """Test cases for calculate_query_depth."""

    def test_flat_query(self):
        doc = parse("{ devices { id name } }")
        op = doc.definitions[0]
        self.assertEqual(calculate_query_depth(op.selection_set), 2)

    def test_nested_query(self):
        doc = parse("{ devices { location { parent { name } } } }")
        op = doc.definitions[0]
        self.assertEqual(calculate_query_depth(op.selection_set), 4)

    def test_mixed_depth_query(self):
        doc = parse("{ devices { id location { name parent { name } } } }")
        op = doc.definitions[0]
        # devices.id = depth 2, devices.location.parent.name = depth 4
        self.assertEqual(calculate_query_depth(op.selection_set), 4)

    def test_empty_selection_set(self):
        self.assertEqual(calculate_query_depth(None), 0)

    def test_inline_fragment(self):
        doc = parse("{ devices { ... on DeviceType { id name } } }")
        op = doc.definitions[0]
        # inline fragment doesn't add depth, same as { devices { id name } } = 2
        self.assertEqual(calculate_query_depth(op.selection_set), 2)

    def test_fragment_spread(self):
        doc = parse("""
            query TestFrag {
                devices { ...DeviceFields }
            }
            fragment DeviceFields on DeviceType {
                id
                name
                location { name }
            }
        """)
        op = doc.definitions[0]
        fragments = {frag.name.value: frag for frag in doc.definitions[1:]}
        # devices.location.name = depth 3
        self.assertEqual(calculate_query_depth(op.selection_set, fragments), 3)


class CalculateQueryComplexityTest(TestCase):
    """Test cases for calculate_query_complexity."""

    def test_flat_query(self):
        doc = parse("{ devices { id name } }")
        op = doc.definitions[0]
        # devices(1) + id(1) + name(1) = 3
        self.assertEqual(calculate_query_complexity(op.selection_set), 3)

    def test_nested_query(self):
        doc = parse("{ devices { id location { name parent { name } } } }")
        op = doc.definitions[0]
        # devices + id + location + name + parent + name = 6
        self.assertEqual(calculate_query_complexity(op.selection_set), 6)

    def test_empty_selection_set(self):
        self.assertEqual(calculate_query_complexity(None), 0)

    def test_multiple_root_fields(self):
        doc = parse("{ devices { id } locations { name } }")
        op = doc.definitions[0]
        # devices + id + locations + name = 4
        self.assertEqual(calculate_query_complexity(op.selection_set), 4)

    def test_fragment_spread(self):
        doc = parse("""
            query TestFrag {
                devices { ...DeviceFields }
            }
            fragment DeviceFields on DeviceType {
                id
                name
            }
        """)
        op = doc.definitions[0]
        fragments = {frag.name.value: frag for frag in doc.definitions[1:]}
        # devices + id + name = 3
        self.assertEqual(calculate_query_complexity(op.selection_set, fragments), 3)
