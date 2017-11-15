# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render_to_response
from django.template import RequestContext
from elasticsearch import Elasticsearch
from paginations import get_pagination
from pods.forms import SearchForm
from pods.models import Pod

import simplejson as json
import urllib2

DEFAULT_PER_PAGE = 12
VIDEOS = Pod.objects.filter(is_draft=False, encodingpods__gt=0).distinct()
ES_URL = getattr(settings, 'ES_URL', ['http://127.0.0.1:9200/'])

# SEARCH

def search_videos(request):
    es = Elasticsearch(ES_URL)
    aggsAttrs = ['owner_full_name', 'type.title',
                 'disciplines.title', 'tags.name', 'channels.title']

    # SEARCH FORM
    search_word = ""
    start_date = None
    end_date = None
    searchForm = SearchForm(request.GET)
    if searchForm.is_valid():
        search_word = searchForm.cleaned_data['q']
        start_date = searchForm.cleaned_data['start_date']
        end_date = searchForm.cleaned_data['end_date']

    # request parameters
    selected_facets = request.GET.getlist(
        'selected_facets') if request.GET.getlist('selected_facets') else []
    page = request.GET.get('page') if request.GET.get('page') else 0
    size = request.COOKIES.get('perpage') if request.COOKIES.get(
        'perpage') and request.COOKIES.get('perpage').isdigit() else DEFAULT_PER_PAGE
    #page = request.GET.get('page')
    try:
        page = int(page.encode('utf-8'))
    except:
        page = 0
    try:
        size = int(size.encode('utf-8'))
    except:
        size = DEFAULT_PER_PAGE

    search_from = page * size

    # Filter query
    filter_search = {}
    filter_query = ""

    if len(selected_facets) > 0 or start_date or end_date:
        filter_search = {"and": []}
        for facet in selected_facets:
            term = facet.split(":")[0]
            value = facet.split(":")[1]
            filter_search["and"].append({
                "term": {
                    "%s" % term: "%s" % value
                }
            })
        if start_date or end_date:
            filter_date_search = {}
            filter_date_search["range"] = {"date_added": {}}
            if start_date:
                filter_date_search["range"]["date_added"][
                    "gte"] = "%04d-%02d-%02d" % (start_date.year, start_date.month, start_date.day)
            if end_date:
                filter_date_search["range"]["date_added"][
                    "lte"] = "%04d-%02d-%02d" % (end_date.year, end_date.month, end_date.day)

            filter_search["and"].append(filter_date_search)

    # Query
    query = {"match_all": {}}
    if search_word != "":
        query = {
            "multi_match": {
                "query":    "%s" % search_word,
                "fields": ["_id", "title^1.1", "owner^0.9", "owner_full_name^0.9", "description^0.6", "tags.name^1",
                           "contributors^0.6", "chapters.title^0.5", "enrichments.title^0.5", "type.title^0.6", "disciplines.title^0.6", "channels.title^0.6"
                           ]
            }
        }

    # bodysearch
    bodysearch = {
        "from": search_from,
        "size": size,
        "query": {},
        "aggs": {},
        "highlight": {
            "pre_tags": ["<strong>"],
            "post_tags": ["</strong>"],
            "fields": {"title": {}}
        }
    }

    bodysearch["query"] = {
        "function_score": {
            "query": {},
            "functions": [
                {
                    "gauss": {
                        "date_added": {
                            "scale": "10d",
                            "offset": "5d",
                            "decay": 0.5
                        }
                    }
                }
            ]
        }
    }

    if filter_search != {}:
        bodysearch["query"]["function_score"]["query"] = {"filtered": {}}
        bodysearch["query"]["function_score"][
            "query"]["filtered"]["query"] = query
        bodysearch["query"]["function_score"]["query"][
            "filtered"]["filter"] = filter_search
    else:
        bodysearch["query"]["function_score"]["query"] = query

    #bodysearch["query"] = query

    for attr in aggsAttrs:
        bodysearch["aggs"][attr.replace(".", "_")] = {
            "terms": {"field": attr + ".raw", "size": 5, "order": {"_count": "asc"}}}

    # add cursus and main_lang 'cursus', 'main_lang',
    bodysearch["aggs"]['cursus'] = {
        "terms": {"field": "cursus", "size": 5, "order": {"_count": "asc"}}}
    bodysearch["aggs"]['main_lang'] = {
        "terms": {"field": "main_lang", "size": 5, "order": {"_count": "asc"}}}

    if settings.DEBUG:
        print json.dumps(bodysearch, indent=4)

    result = es.search(index="pod", body=bodysearch)

    if settings.DEBUG:
        print json.dumps(result, indent=4)

    remove_selected_facet = ""
    for facet in selected_facets:
        term = facet.split(":")[0]
        value = facet.split(":")[1]
        agg_term = term.replace(".raw", "")
        if result["aggregations"].get(agg_term):
            del result["aggregations"][agg_term]
        else:
            if agg_term == "type.slug":
                del result["aggregations"]["type_title"]
            if agg_term == "tags.slug":
                del result["aggregations"]["tags_name"]
            if agg_term == "disciplines.slug":
                del result["aggregations"]["disciplines_title"]

        # Create link to remove facet
        url_value = value
        if agg_term == "cursus":
            for tab in settings.CURSUS_CODES:
                if tab[0] == value:
                    value = tab[1]
        if agg_term == "main_lang":
            for tab in settings.ALL_LANG_CHOICES:
                if tab[0] == value:
                    value = tab[1]

        url_value = u'%s'.decode('latin1') % url_value
        url_value = url_value.encode('utf-8')
        url_value = urllib2.quote(url_value)
        link = request.get_full_path().replace(
            "&selected_facets=%s:%s" % (term, url_value), "")
        msg_title = (u'Remove selection')
        remove_selected_facet += u'&nbsp;<a href="%s" title="%s"><span class="glyphicon glyphicon-remove" aria-hidden="true"></span>%s</a>&nbsp;' % (
            link, msg_title, value)

    # Pagination mayby better idea ?
    objects = []
    for i in range(0, result["hits"]["total"]):
        objects.append(i)
    paginator = Paginator(objects, size)
    try:
        search_pagination = paginator.page(page + 1)
    except:
        search_pagination = paginator.page(paginator.num_pages)

    return render_to_response("search/search_video.html",
                              {"result": result, "page": page,
                                  "search_pagination": search_pagination, "form": searchForm, "remove_selected_facet": remove_selected_facet},
                              context_instance=RequestContext(request))