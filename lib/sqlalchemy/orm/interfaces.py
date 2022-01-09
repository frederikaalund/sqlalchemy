# orm/interfaces.py
# Copyright (C) 2005-2022 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""

Contains various base classes used throughout the ORM.

Defines some key base classes prominent within the internals.

This module and the classes within are mostly private, though some attributes
are exposed when inspecting mappings.

"""

import collections
import typing
from typing import Any
from typing import cast
from typing import TypeVar

from . import exc as orm_exc
from . import path_registry
from .base import _MappedAttribute  # noqa
from .base import EXT_CONTINUE
from .base import EXT_SKIP
from .base import EXT_STOP
from .base import InspectionAttr  # noqa
from .base import InspectionAttrInfo  # noqa
from .base import MANYTOMANY
from .base import MANYTOONE
from .base import NOT_EXTENSION
from .base import ONETOMANY
from .base import SQLORMOperations
from .. import inspect
from .. import inspection
from .. import util
from ..sql import operators
from ..sql import roles
from ..sql import visitors
from ..sql.base import ExecutableOption
from ..sql.cache_key import HasCacheKey

_T = TypeVar("_T", bound=Any)

__all__ = (
    "EXT_CONTINUE",
    "EXT_STOP",
    "EXT_SKIP",
    "ONETOMANY",
    "MANYTOMANY",
    "MANYTOONE",
    "NOT_EXTENSION",
    "LoaderStrategy",
    "MapperOption",
    "LoaderOption",
    "MapperProperty",
    "PropComparator",
    "StrategizedProperty",
)


class ORMStatementRole(roles.StatementRole):
    _role_name = (
        "Executable SQL or text() construct, including ORM " "aware objects"
    )


class ORMColumnsClauseRole(roles.ColumnsClauseRole):
    _role_name = "ORM mapped entity, aliased entity, or Column expression"


class ORMEntityColumnsClauseRole(ORMColumnsClauseRole):
    _role_name = "ORM mapped or aliased entity"


class ORMFromClauseRole(roles.StrictFromClauseRole):
    _role_name = "ORM mapped entity, aliased entity, or FROM expression"


@inspection._self_inspects
class MapperProperty(
    HasCacheKey, _MappedAttribute[_T], InspectionAttr, util.MemoizedSlots
):
    """Represent a particular class attribute mapped by :class:`_orm.Mapper`.

    The most common occurrences of :class:`.MapperProperty` are the
    mapped :class:`_schema.Column`, which is represented in a mapping as
    an instance of :class:`.ColumnProperty`,
    and a reference to another class produced by :func:`_orm.relationship`,
    represented in the mapping as an instance of
    :class:`.RelationshipProperty`.

    """

    __slots__ = (
        "_configure_started",
        "_configure_finished",
        "parent",
        "key",
        "info",
    )

    _cache_key_traversal = [
        ("parent", visitors.ExtendedInternalTraversal.dp_has_cache_key),
        ("key", visitors.ExtendedInternalTraversal.dp_string),
    ]

    cascade = frozenset()
    """The set of 'cascade' attribute names.

    This collection is checked before the 'cascade_iterator' method is called.

    The collection typically only applies to a RelationshipProperty.

    """

    is_property = True
    """Part of the InspectionAttr interface; states this object is a
    mapper property.

    """

    @property
    def _links_to_entity(self):
        """True if this MapperProperty refers to a mapped entity.

        Should only be True for RelationshipProperty, False for all others.

        """
        raise NotImplementedError()

    def _memoized_attr_info(self):
        """Info dictionary associated with the object, allowing user-defined
        data to be associated with this :class:`.InspectionAttr`.

        The dictionary is generated when first accessed.  Alternatively,
        it can be specified as a constructor argument to the
        :func:`.column_property`, :func:`_orm.relationship`, or
        :func:`.composite`
        functions.

        .. versionchanged:: 1.0.0 :attr:`.MapperProperty.info` is also
           available on extension types via the
           :attr:`.InspectionAttrInfo.info` attribute, so that it can apply
           to a wider variety of ORM and extension constructs.

        .. seealso::

            :attr:`.QueryableAttribute.info`

            :attr:`.SchemaItem.info`

        """
        return {}

    def setup(self, context, query_entity, path, adapter, **kwargs):
        """Called by Query for the purposes of constructing a SQL statement.

        Each MapperProperty associated with the target mapper processes the
        statement referenced by the query context, adding columns and/or
        criterion as appropriate.

        """

    def create_row_processor(
        self, context, query_entity, path, mapper, result, adapter, populators
    ):
        """Produce row processing functions and append to the given
        set of populators lists.

        """

    def cascade_iterator(
        self, type_, state, dict_, visited_states, halt_on=None
    ):
        """Iterate through instances related to the given instance for
        a particular 'cascade', starting with this MapperProperty.

        Return an iterator3-tuples (instance, mapper, state).

        Note that the 'cascade' collection on this MapperProperty is
        checked first for the given type before cascade_iterator is called.

        This method typically only applies to RelationshipProperty.

        """

        return iter(())

    def set_parent(self, parent, init):
        """Set the parent mapper that references this MapperProperty.

        This method is overridden by some subclasses to perform extra
        setup when the mapper is first known.

        """
        self.parent = parent

    def instrument_class(self, mapper):
        """Hook called by the Mapper to the property to initiate
        instrumentation of the class attribute managed by this
        MapperProperty.

        The MapperProperty here will typically call out to the
        attributes module to set up an InstrumentedAttribute.

        This step is the first of two steps to set up an InstrumentedAttribute,
        and is called early in the mapper setup process.

        The second step is typically the init_class_attribute step,
        called from StrategizedProperty via the post_instrument_class()
        hook.  This step assigns additional state to the InstrumentedAttribute
        (specifically the "impl") which has been determined after the
        MapperProperty has determined what kind of persistence
        management it needs to do (e.g. scalar, object, collection, etc).

        """

    def __init__(self):
        self._configure_started = False
        self._configure_finished = False

    def init(self):
        """Called after all mappers are created to assemble
        relationships between mappers and perform other post-mapper-creation
        initialization steps.


        """
        self._configure_started = True
        self.do_init()
        self._configure_finished = True

    @property
    def class_attribute(self):
        """Return the class-bound descriptor corresponding to this
        :class:`.MapperProperty`.

        This is basically a ``getattr()`` call::

            return getattr(self.parent.class_, self.key)

        I.e. if this :class:`.MapperProperty` were named ``addresses``,
        and the class to which it is mapped is ``User``, this sequence
        is possible::

            >>> from sqlalchemy import inspect
            >>> mapper = inspect(User)
            >>> addresses_property = mapper.attrs.addresses
            >>> addresses_property.class_attribute is User.addresses
            True
            >>> User.addresses.property is addresses_property
            True


        """

        return getattr(self.parent.class_, self.key)

    def do_init(self):
        """Perform subclass-specific initialization post-mapper-creation
        steps.

        This is a template method called by the ``MapperProperty``
        object's init() method.

        """

    def post_instrument_class(self, mapper):
        """Perform instrumentation adjustments that need to occur
        after init() has completed.

        The given Mapper is the Mapper invoking the operation, which
        may not be the same Mapper as self.parent in an inheritance
        scenario; however, Mapper will always at least be a sub-mapper of
        self.parent.

        This method is typically used by StrategizedProperty, which delegates
        it to LoaderStrategy.init_class_attribute() to perform final setup
        on the class-bound InstrumentedAttribute.

        """

    def merge(
        self,
        session,
        source_state,
        source_dict,
        dest_state,
        dest_dict,
        load,
        _recursive,
        _resolve_conflict_map,
    ):
        """Merge the attribute represented by this ``MapperProperty``
        from source to destination object.

        """

    def __repr__(self):
        return "<%s at 0x%x; %s>" % (
            self.__class__.__name__,
            id(self),
            getattr(self, "key", "no key"),
        )


@inspection._self_inspects
class PropComparator(
    SQLORMOperations[_T], operators.ColumnOperators[SQLORMOperations]
):
    r"""Defines SQL operations for ORM mapped attributes.

    SQLAlchemy allows for operators to
    be redefined at both the Core and ORM level.  :class:`.PropComparator`
    is the base class of operator redefinition for ORM-level operations,
    including those of :class:`.ColumnProperty`,
    :class:`.RelationshipProperty`, and :class:`.CompositeProperty`.

    User-defined subclasses of :class:`.PropComparator` may be created. The
    built-in Python comparison and math operator methods, such as
    :meth:`.operators.ColumnOperators.__eq__`,
    :meth:`.operators.ColumnOperators.__lt__`, and
    :meth:`.operators.ColumnOperators.__add__`, can be overridden to provide
    new operator behavior. The custom :class:`.PropComparator` is passed to
    the :class:`.MapperProperty` instance via the ``comparator_factory``
    argument. In each case,
    the appropriate subclass of :class:`.PropComparator` should be used::

        # definition of custom PropComparator subclasses

        from sqlalchemy.orm.properties import \
                                ColumnProperty,\
                                CompositeProperty,\
                                RelationshipProperty

        class MyColumnComparator(ColumnProperty.Comparator):
            def __eq__(self, other):
                return self.__clause_element__() == other

        class MyRelationshipComparator(RelationshipProperty.Comparator):
            def any(self, expression):
                "define the 'any' operation"
                # ...

        class MyCompositeComparator(CompositeProperty.Comparator):
            def __gt__(self, other):
                "redefine the 'greater than' operation"

                return sql.and_(*[a>b for a, b in
                                  zip(self.__clause_element__().clauses,
                                      other.__composite_values__())])


        # application of custom PropComparator subclasses

        from sqlalchemy.orm import column_property, relationship, composite
        from sqlalchemy import Column, String

        class SomeMappedClass(Base):
            some_column = column_property(Column("some_column", String),
                                comparator_factory=MyColumnComparator)

            some_relationship = relationship(SomeOtherClass,
                                comparator_factory=MyRelationshipComparator)

            some_composite = composite(
                    Column("a", String), Column("b", String),
                    comparator_factory=MyCompositeComparator
                )

    Note that for column-level operator redefinition, it's usually
    simpler to define the operators at the Core level, using the
    :attr:`.TypeEngine.comparator_factory` attribute.  See
    :ref:`types_operators` for more detail.

    .. seealso::

        :class:`.ColumnProperty.Comparator`

        :class:`.RelationshipProperty.Comparator`

        :class:`.CompositeProperty.Comparator`

        :class:`.ColumnOperators`

        :ref:`types_operators`

        :attr:`.TypeEngine.comparator_factory`

    """

    __slots__ = "prop", "property", "_parententity", "_adapt_to_entity"

    __visit_name__ = "orm_prop_comparator"

    def __init__(
        self,
        prop,
        parentmapper,
        adapt_to_entity=None,
    ):
        self.prop = self.property = prop
        self._parententity = adapt_to_entity or parentmapper
        self._adapt_to_entity = adapt_to_entity

    def __clause_element__(self):
        raise NotImplementedError("%r" % self)

    def _bulk_update_tuples(self, value):
        """Receive a SQL expression that represents a value in the SET
        clause of an UPDATE statement.

        Return a tuple that can be passed to a :class:`_expression.Update`
        construct.

        """

        return [(self.__clause_element__(), value)]

    def adapt_to_entity(self, adapt_to_entity):
        """Return a copy of this PropComparator which will use the given
        :class:`.AliasedInsp` to produce corresponding expressions.
        """
        return self.__class__(self.prop, self._parententity, adapt_to_entity)

    @property
    def _parentmapper(self):
        """legacy; this is renamed to _parententity to be
        compatible with QueryableAttribute."""
        return inspect(self._parententity).mapper

    @property
    def _propagate_attrs(self):
        # this suits the case in coercions where we don't actually
        # call ``__clause_element__()`` but still need to get
        # resolved._propagate_attrs.  See #6558.
        return util.immutabledict(
            {
                "compile_state_plugin": "orm",
                "plugin_subject": self._parentmapper,
            }
        )

    @property
    def adapter(self):
        """Produce a callable that adapts column expressions
        to suit an aliased version of this comparator.

        """
        if self._adapt_to_entity is None:
            return None
        else:
            return self._adapt_to_entity._adapt_element

    @property
    def info(self):
        return self.property.info

    @staticmethod
    def _any_op(a, b, **kwargs):
        return a.any(b, **kwargs)

    @staticmethod
    def _has_op(left, other, **kwargs):
        return left.has(other, **kwargs)

    @staticmethod
    def _of_type_op(a, class_):
        return a.of_type(class_)

    any_op = cast(operators.OperatorType, _any_op)
    has_op = cast(operators.OperatorType, _has_op)
    of_type_op = cast(operators.OperatorType, _of_type_op)

    if typing.TYPE_CHECKING:

        def operate(
            self, op: operators.OperatorType, *other: Any, **kwargs: Any
        ) -> "SQLORMOperations":
            ...

        def reverse_operate(
            self, op: operators.OperatorType, other: Any, **kwargs: Any
        ) -> "SQLORMOperations":
            ...

    def of_type(self, class_) -> "SQLORMOperations[_T]":
        r"""Redefine this object in terms of a polymorphic subclass,
        :func:`_orm.with_polymorphic` construct, or :func:`_orm.aliased`
        construct.

        Returns a new PropComparator from which further criterion can be
        evaluated.

        e.g.::

            query.join(Company.employees.of_type(Engineer)).\
               filter(Engineer.name=='foo')

        :param \class_: a class or mapper indicating that criterion will be
            against this specific subclass.

        .. seealso::

            :ref:`queryguide_join_onclause` - in the :ref:`queryguide_toplevel`

            :ref:`inheritance_of_type`

        """

        return self.operate(PropComparator.of_type_op, class_)

    def and_(self, *criteria) -> "SQLORMOperations[_T]":
        """Add additional criteria to the ON clause that's represented by this
        relationship attribute.

        E.g.::


            stmt = select(User).join(
                User.addresses.and_(Address.email_address != 'foo')
            )

            stmt = select(User).options(
                joinedload(User.addresses.and_(Address.email_address != 'foo'))
            )

        .. versionadded:: 1.4

        .. seealso::

            :ref:`orm_queryguide_join_on_augmented`

            :ref:`loader_option_criteria`

            :func:`.with_loader_criteria`

        """
        return self.operate(operators.and_, *criteria)

    def any(self, criterion=None, **kwargs) -> "SQLORMOperations[_T]":
        r"""Return true if this collection contains any member that meets the
        given criterion.

        The usual implementation of ``any()`` is
        :meth:`.RelationshipProperty.Comparator.any`.

        :param criterion: an optional ClauseElement formulated against the
          member class' table or attributes.

        :param \**kwargs: key/value pairs corresponding to member class
          attribute names which will be compared via equality to the
          corresponding values.

        """

        return self.operate(PropComparator.any_op, criterion, **kwargs)

    def has(self, criterion=None, **kwargs) -> "SQLORMOperations[_T]":
        r"""Return true if this element references a member which meets the
        given criterion.

        The usual implementation of ``has()`` is
        :meth:`.RelationshipProperty.Comparator.has`.

        :param criterion: an optional ClauseElement formulated against the
          member class' table or attributes.

        :param \**kwargs: key/value pairs corresponding to member class
          attribute names which will be compared via equality to the
          corresponding values.

        """

        return self.operate(PropComparator.has_op, criterion, **kwargs)


class StrategizedProperty(MapperProperty[_T]):
    """A MapperProperty which uses selectable strategies to affect
    loading behavior.

    There is a single strategy selected by default.  Alternate
    strategies can be selected at Query time through the usage of
    ``StrategizedOption`` objects via the Query.options() method.

    The mechanics of StrategizedProperty are used for every Query
    invocation for every mapped attribute participating in that Query,
    to determine first how the attribute will be rendered in SQL
    and secondly how the attribute will retrieve a value from a result
    row and apply it to a mapped object.  The routines here are very
    performance-critical.

    """

    __slots__ = (
        "_strategies",
        "strategy",
        "_wildcard_token",
        "_default_path_loader_key",
    )
    inherit_cache = True
    strategy_wildcard_key = None

    def _memoized_attr__wildcard_token(self):
        return (
            f"{self.strategy_wildcard_key}:{path_registry._WILDCARD_TOKEN}",
        )

    def _memoized_attr__default_path_loader_key(self):
        return (
            "loader",
            (f"{self.strategy_wildcard_key}:{path_registry._DEFAULT_TOKEN}",),
        )

    def _get_context_loader(self, context, path):
        load = None

        search_path = path[self]

        # search among: exact match, "attr.*", "default" strategy
        # if any.
        for path_key in (
            search_path._loader_key,
            search_path._wildcard_path_loader_key,
            search_path._default_path_loader_key,
        ):
            if path_key in context.attributes:
                load = context.attributes[path_key]
                break

                # note that if strategy_options.Load is placing non-actionable
                # objects in the context like defaultload(), we would
                # need to continue the loop here if we got such an
                # option as below.
                # if load.strategy or load.local_opts:
                #    break

        return load

    def _get_strategy(self, key):
        try:
            return self._strategies[key]
        except KeyError:
            pass

        # run outside to prevent transfer of exception context
        cls = self._strategy_lookup(self, *key)
        # this previously was setting self._strategies[cls], that's
        # a bad idea; should use strategy key at all times because every
        # strategy has multiple keys at this point
        self._strategies[key] = strategy = cls(self, key)
        return strategy

    def setup(self, context, query_entity, path, adapter, **kwargs):
        loader = self._get_context_loader(context, path)
        if loader and loader.strategy:
            strat = self._get_strategy(loader.strategy)
        else:
            strat = self.strategy
        strat.setup_query(
            context, query_entity, path, loader, adapter, **kwargs
        )

    def create_row_processor(
        self, context, query_entity, path, mapper, result, adapter, populators
    ):
        loader = self._get_context_loader(context, path)
        if loader and loader.strategy:
            strat = self._get_strategy(loader.strategy)
        else:
            strat = self.strategy
        strat.create_row_processor(
            context,
            query_entity,
            path,
            loader,
            mapper,
            result,
            adapter,
            populators,
        )

    def do_init(self):
        self._strategies = {}
        self.strategy = self._get_strategy(self.strategy_key)

    def post_instrument_class(self, mapper):
        if (
            not self.parent.non_primary
            and not mapper.class_manager._attr_has_impl(self.key)
        ):
            self.strategy.init_class_attribute(mapper)

    _all_strategies = collections.defaultdict(dict)

    @classmethod
    def strategy_for(cls, **kw):
        def decorate(dec_cls):
            # ensure each subclass of the strategy has its
            # own _strategy_keys collection
            if "_strategy_keys" not in dec_cls.__dict__:
                dec_cls._strategy_keys = []
            key = tuple(sorted(kw.items()))
            cls._all_strategies[cls][key] = dec_cls
            dec_cls._strategy_keys.append(key)
            return dec_cls

        return decorate

    @classmethod
    def _strategy_lookup(cls, requesting_property, *key):
        requesting_property.parent._with_polymorphic_mappers

        for prop_cls in cls.__mro__:
            if prop_cls in cls._all_strategies:
                strategies = cls._all_strategies[prop_cls]
                try:
                    return strategies[key]
                except KeyError:
                    pass

        for property_type, strats in cls._all_strategies.items():
            if key in strats:
                intended_property_type = property_type
                actual_strategy = strats[key]
                break
        else:
            intended_property_type = None
            actual_strategy = None

        raise orm_exc.LoaderStrategyException(
            cls,
            requesting_property,
            intended_property_type,
            actual_strategy,
            key,
        )


class ORMOption(ExecutableOption):
    """Base class for option objects that are passed to ORM queries.

    These options may be consumed by :meth:`.Query.options`,
    :meth:`.Select.options`, or in a more general sense by any
    :meth:`.Executable.options` method.   They are interpreted at
    statement compile time or execution time in modern use.  The
    deprecated :class:`.MapperOption` is consumed at ORM query construction
    time.

    .. versionadded:: 1.4

    """

    __slots__ = ()

    _is_legacy_option = False

    propagate_to_loaders = False
    """if True, indicate this option should be carried along
    to "secondary" SELECT statements that occur for relationship
    lazy loaders as well as attribute load / refresh operations.

    """

    _is_compile_state = False

    _is_criteria_option = False

    _is_strategy_option = False


class CompileStateOption(HasCacheKey, ORMOption):
    """base for :class:`.ORMOption` classes that affect the compilation of
    a SQL query and therefore need to be part of the cache key.

    .. note::  :class:`.CompileStateOption` is generally non-public and
       should not be used as a base class for user-defined options; instead,
       use :class:`.UserDefinedOption`, which is easier to use as it does not
       interact with ORM compilation internals or caching.

    :class:`.CompileStateOption` defines an internal attribute
    ``_is_compile_state=True`` which has the effect of the ORM compilation
    routines for SELECT and other statements will call upon these options when
    a SQL string is being compiled. As such, these classes implement
    :class:`.HasCacheKey` and need to provide robust ``_cache_key_traversal``
    structures.

    The :class:`.CompileStateOption` class is used to implement the ORM
    :class:`.LoaderOption` and :class:`.CriteriaOption` classes.

    .. versionadded:: 1.4.28


    """

    _is_compile_state = True

    def process_compile_state(self, compile_state):
        """Apply a modification to a given :class:`.CompileState`.

        This method is part of the implementation of a particular
        :class:`.CompileStateOption` and is only invoked internally
        when an ORM query is compiled.

        """

    def process_compile_state_replaced_entities(
        self, compile_state, mapper_entities
    ):
        """Apply a modification to a given :class:`.CompileState`,
        given entities that were replaced by with_only_columns() or
        with_entities().

        This method is part of the implementation of a particular
        :class:`.CompileStateOption` and is only invoked internally
        when an ORM query is compiled.

        .. versionadded:: 1.4.19

        """


class LoaderOption(CompileStateOption):
    """Describe a loader modification to an ORM statement at compilation time.

    .. versionadded:: 1.4

    """

    def process_compile_state_replaced_entities(
        self, compile_state, mapper_entities
    ):
        self.process_compile_state(compile_state)


class CriteriaOption(CompileStateOption):
    """Describe a WHERE criteria modification to an ORM statement at
    compilation time.

    .. versionadded:: 1.4

    """

    _is_criteria_option = True

    def get_global_criteria(self, attributes):
        """update additional entity criteria options in the given
        attributes dictionary.

        """


class UserDefinedOption(ORMOption):
    """Base class for a user-defined option that can be consumed from the
    :meth:`.SessionEvents.do_orm_execute` event hook.

    """

    _is_legacy_option = False

    propagate_to_loaders = False
    """if True, indicate this option should be carried along
    to "secondary" Query objects produced during lazy loads
    or refresh operations.

    """

    def __init__(self, payload=None):
        self.payload = payload


@util.deprecated_cls(
    "1.4",
    "The :class:`.MapperOption class is deprecated and will be removed "
    "in a future release.   For "
    "modifications to queries on a per-execution basis, use the "
    ":class:`.UserDefinedOption` class to establish state within a "
    ":class:`.Query` or other Core statement, then use the "
    ":meth:`.SessionEvents.before_orm_execute` hook to consume them.",
    constructor=None,
)
class MapperOption(ORMOption):
    """Describe a modification to a Query"""

    _is_legacy_option = True

    propagate_to_loaders = False
    """if True, indicate this option should be carried along
    to "secondary" Query objects produced during lazy loads
    or refresh operations.

    """

    def process_query(self, query):
        """Apply a modification to the given :class:`_query.Query`."""

    def process_query_conditionally(self, query):
        """same as process_query(), except that this option may not
        apply to the given query.

        This is typically applied during a lazy load or scalar refresh
        operation to propagate options stated in the original Query to the
        new Query being used for the load.  It occurs for those options that
        specify propagate_to_loaders=True.

        """

        self.process_query(query)


class LoaderStrategy:
    """Describe the loading behavior of a StrategizedProperty object.

    The ``LoaderStrategy`` interacts with the querying process in three
    ways:

    * it controls the configuration of the ``InstrumentedAttribute``
      placed on a class to handle the behavior of the attribute.  this
      may involve setting up class-level callable functions to fire
      off a select operation when the attribute is first accessed
      (i.e. a lazy load)

    * it processes the ``QueryContext`` at statement construction time,
      where it can modify the SQL statement that is being produced.
      For example, simple column attributes will add their represented
      column to the list of selected columns, a joined eager loader
      may establish join clauses to add to the statement.

    * It produces "row processor" functions at result fetching time.
      These "row processor" functions populate a particular attribute
      on a particular mapped instance.

    """

    __slots__ = (
        "parent_property",
        "is_class_level",
        "parent",
        "key",
        "strategy_key",
        "strategy_opts",
    )

    def __init__(self, parent, strategy_key):
        self.parent_property = parent
        self.is_class_level = False
        self.parent = self.parent_property.parent
        self.key = self.parent_property.key
        self.strategy_key = strategy_key
        self.strategy_opts = dict(strategy_key)

    def init_class_attribute(self, mapper):
        pass

    def setup_query(
        self, compile_state, query_entity, path, loadopt, adapter, **kwargs
    ):
        """Establish column and other state for a given QueryContext.

        This method fulfills the contract specified by MapperProperty.setup().

        StrategizedProperty delegates its setup() method
        directly to this method.

        """

    def create_row_processor(
        self,
        context,
        query_entity,
        path,
        loadopt,
        mapper,
        result,
        adapter,
        populators,
    ):
        """Establish row processing functions for a given QueryContext.

        This method fulfills the contract specified by
        MapperProperty.create_row_processor().

        StrategizedProperty delegates its create_row_processor() method
        directly to this method.

        """

    def __str__(self):
        return str(self.parent_property)
