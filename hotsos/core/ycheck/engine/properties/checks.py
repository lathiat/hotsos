from hotsos.core.log import log
from hotsos.core.searchtools import FileSearcher
from hotsos.core.ycheck.engine.properties.common import (
    cached_yproperty_attr,
    YPropertyOverrideBase,
    YPropertyMappedOverrideBase,
    YDefsSection,
    add_to_property_catalog,
    YDefsContext,
)
from hotsos.core.ycheck.engine.properties.requires.requires import (
    YPropertyRequires
)
from hotsos.core.ycheck.engine.properties.search import YPropertySearch
from hotsos.core.ycheck.engine.properties.input import YPropertyInput


@add_to_property_catalog
class YPropertyCheck(YPropertyMappedOverrideBase):

    @cached_yproperty_attr
    def search_results(self):
        """
        Retrieve the search results for the search property within this check.
        """
        global_results = self.context.search_results
        if global_results is not None:
            log.debug("extracting check search results")
            tag = self.search.unique_search_tag
            _results = global_results.find_by_tag(tag)
            return self.search.apply_constraints(_results)

        raise Exception("no search results provided to check '{}'".
                        format(self.check_name))

    @classmethod
    def _override_keys(cls):
        return ['check']

    @classmethod
    def _override_mapped_member_types(cls):
        return [YPropertyRequires, YPropertySearch, YPropertyInput]

    @property
    def name(self):
        if hasattr(self, 'check_name'):
            return getattr(self, 'check_name')

    def _set_search_cache_info(self, results):
        """
        @param results: search results for query in search property found in
                        this check.
        """
        self.search.cache.set('num_results', len(self.search_results))
        if results:
            # The following aggregates results by group/index and stores in
            # the property cache to make them accessible via
            # PropertyCacheRefResolver.
            results_by_idx = {}
            for result in results:
                for idx, value in enumerate(result):
                    if idx not in results_by_idx:
                        results_by_idx[idx] = set()

                    results_by_idx[idx].add(value)

            for idx in results_by_idx:
                self.search.cache.set('results_group_{}'.format(idx),
                                      list(results_by_idx[idx]))

        # make it available from this property
        self.cache.set('search', self.search.cache)

    def _result(self):
        if self.search:
            self._set_search_cache_info(self.search_results)
            if not self.search_results:
                log.debug("check %s search has no matches so result=False",
                          self.name)
                return False

            return True
        elif self.requires:
            if self.cache.requires:
                result = self.cache.requires.passes
                log.debug("check %s - using cached result=%s", self.name,
                          result)
            else:
                result = self.requires.passes
                self.cache.set('requires', self.requires.cache)

            return result
        else:
            raise Exception("no supported properties found in check {}".format(
                            self.name))

    @property
    def result(self):
        log.debug("executing check %s", self.name)
        result = self._result()
        log.debug("check %s result=%s", self.name, result)
        return result


@add_to_property_catalog
class YPropertyChecks(YPropertyOverrideBase):

    @classmethod
    def _override_keys(cls):
        return ['checks']

    def initialise(self, vars, input):
        """
        Perform initialisation tasks for this set of checks.

        * create context containing vars for each check
        * pre-load searches from all/any checks and get results. This needs to
          be done before check results are consumed.
        """
        self.check_context = YDefsContext({'vars': vars})

        log.debug("loading checks searchdefs into filesearcher")
        s = FileSearcher()
        # first load all the search definitions into the searcher
        for c in self._checks:
            if c.search:
                # local takes precedence over global
                _input = c.input or input
                for path in _input.paths:
                    c.search.load_searcher(s, path)

        # provide results to each check object using global context
        log.debug("executing check searches")
        YDefsContext.search_results = s.search()

    @cached_yproperty_attr
    def _checks(self):
        log.debug("parsing checks section")
        if not hasattr(self, 'check_context'):
            raise Exception("checks not yet initialised")

        resolved = []
        for name, content in self.content.items():
            s = YDefsSection(self._override_name, {name: {'check': content}},
                             context=self.check_context)
            for c in s.leaf_sections:
                c.check.check_name = c.name
                resolved.append(c.check)

        return resolved

    def __iter__(self):
        log.debug("iterating over checks")
        for c in self._checks:
            log.debug("returning check %s", c.name)
            yield c
