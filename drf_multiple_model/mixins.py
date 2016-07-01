from rest_framework.response import Response

from itertools import chain

from django.db import connection

class MultipleModelMixin(object):
    """
    Create a list of objects from multiple models/serializers.

    Mixin is expecting the view will have a queryList variable, which is
    a list/tuple of queryset/serailizer pairs, like as below:

    queryList = [
            (querysetA,serializerA),
            (querysetB,serializerB),
            (querysetC,serializerC),
            .....
    ]

    optionally, you can add a third element to the queryList, a dict with params 'label' or 'filter_class':

    params = {
        'label': 'labelA',
        'filter_class': FilterClassA
    }

    queryList = [
            (querysetA,serializerA, paramsA),
            (querysetB,serializerB, paramsB),
            (querysetC,serializerC),
            .....
    ]

    """

    queryList = None

    # Flag to determine whether to mix objects together or keep them distinct
    flat = False

    # Optional keyword to sort flat lasts by given attribute
    # note that the attribute must by shared by ALL models
    sorting_field = None

    # Flag to append the particular django model being used to the data
    add_model_type = True

    def get_queryList(self):
        assert self.queryList is not None, (
            "'%s' should either include a `queryList` attribute, "
            "or override the `get_queryList()` method."
            % self.__class__.__name__
        )

        queryList = self.queryList

        return queryList

    def list(self, request, *args, **kwargs):
        queryList = self.get_queryList()

        self._default_filter_class = getattr(self, 'filter_class', None)

        # Iterate through the queryList, run each queryset and serialize the data
        results = []
        for opt in queryList:
            # Get additional params
            try:
                obj_to_inspect = opt[2]
                if isinstance(obj_to_inspect, str):
                    params = {'label': obj_to_inspect}
                else:
                    params = obj_to_inspect
            except IndexError:
                params = {}

            self.set_filter_class(params)

            # Run the queryset through Django Rest Framework filters
            queryset = self.filter_queryset(opt[0])

            label = self.get_label(queryset.model.__name__.lower(), params)

            # Run the paired serializer
            data = opt[1](queryset, many=True).data

            # if flat=True, Organize the data in a flat manner
            if self.flat:
                for datum in data:
                    if label:
                        datum.update({'type': label})
                    results.append(datum)

            # Otherwise, group the data by Model/Queryset
            else:
                if label:
                    data = {label: data}

                results.append(data)

        # Sort by given attribute, if sorting_attribute is provided
        if self.sorting_field and self.flat:
            results = sorted(results, key=lambda datum: datum[self.sorting_field])

        return Response(results)

    def get_label(self, model_label, params):
        """
        Get the label from params, unless add_model_type is note set
        """
        label = params.get('label')
        if not label and self.add_model_type:
            return model_label
        return label

    def set_filter_class(self, params):
        """
        Set self.filter_class attribute if filter_class was set in params
        """
        self.filter_class = params.get('filter_class', self._default_filter_class)
