from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.syndication.views import Feed, add_domain
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files import File
from django.db.models import Max, Min
from django.utils.feedgenerator import Rss201rev2Feed, Atom1Feed
from string import replace
from datetime import date, datetime
from HTMLParser import HTMLParser
from models import * 

unescape = HTMLParser().unescape

VIDEOS = Pod.objects.filter(is_draft=False, encodingpods__gt=0).distinct()

class MySelectFeed(Feed):
    title = "RSS Feed generated by Pod"
    link = "/rss/"
    description = "RSS Feed description."
    author_name = settings.TITLE_ETB
    author_email = settings.DEFAULT_FROM_EMAIL 
    author_link = "/"
    categories = ["Education"]
    feed_copyright = "Creative Commons Attribution 4.0 International"

    def get_object(self, request, qparam):

	self.request = request
	self.current_site = get_current_site(self.request)
        VIDEOS = Pod.objects.filter(is_draft=False, encodingpods__gt=0).distinct()
        filtres = ""	

	# Filtres 
	if qparam:
	    filtres = qparam.replace("'] ", "']&")

	return filtres

    def title(self, obj):

	if obj:
	    obj = obj.encode('utf8')
	    param = obj.split("&")

	    for p in param:
		k,v = p.split('=')
		if k == 'channel':
		    channel = get_object_or_404(Channel, slug=v)
		    title = channel.title
		else:
		    title = 'Result of search request on Pod'
        else:
	    title = 'No title for this feed'

	return title

    def description(self, obj):

        description = ''
	if obj:
	    obj = obj.encode('utf8')
	    param = obj.split("&")

	    for p in param:
		k,v = p.split('=')
		if k == 'channel':
		    channel = get_object_or_404(Channel, slug=v)
		    description = unescape(channel.description.replace('<p>', ''))
		    description = description.replace('</p>', '')
                else:
		    description = description + str(k) + ' : ' + str(v) + ' '
        else:
	    description = 'No summary for this feed.'
	
	return description

    def items(self, obj):

        VIDEOS = Pod.objects.filter(is_draft=False, encodingpods__gt=0).distinct()
    	self.title = ''
	self.description = ''

	if obj:
	    obj = obj.encode('utf8')
	    param = obj.split("&")

	    for p in param:
	        print "p : %s" % (p,)
		k,v = p.split('=')
		print "k : %s, v : %s" % (k,v)

		if k == 'channel':
		    channel = get_object_or_404(Channel, slug=v)
		    VIDEOS = VIDEOS.filter(channel=channel)
                    self.title = channel.title
		    self.description = unescape(channel.description.replace("<p>", ""))
		    self.description = self.description.replace("</p>", "")
		    
		else:
		    self.title = 'Result of search request'
		    self.description = self.description + k + ': ' + v + ' '
		    v = (((v.replace('\'', '')).replace('[', '')).replace(']', '')).replace(', ', ',')
		    lv = v.split(',')
		    #print 'lv :' + str(lv)
		    if k == 'theme':
		        theme = get_object_or_404(Theme, slug=v)
		        VIDEOS = VIDEOS.filter(theme=theme)
		    if k == 'type':
			VIDEOS = VIDEOS.filter(type__slug__in=lv)
		    if k == 'discipline':
		        VIDEOS = VIDEOS.filter(discipline__slug__in=lv)
		    if k == 'owner':
		        VIDEOS = VIDEOS.filter(owner__username__in=lv)
		    if k == 'tag':
		        v = v.encode('utf8')
		        VIDEOS = VIDEOS.filter(tags__slug__in=lv)
        
	return VIDEOS

    def item_title(self, item):
        return item.owner.get_full_name() + ' | ' + item.title

    def item_author_name(self, item):
        return item.owner.get_full_name()

    
    def item_description(self, item):
        description = item.description + 'duration : ' + item.duration_in_time()
	return description

    def item_pubdate(self, item):
        return datetime.strptime(item.date_added.strftime('%Y-%m-%d'), '%Y-%m-%d')


class iTunesFeed(Rss201rev2Feed):  

    def rss_attributes(self):
	return {
	    'version': self._version,
	    'xmlns:atom': 'http://www.w3.org/2005/Atom',
	    'xmlns:itunes': u'http://www.itunes.com/dtds/podcast-1.0.dtd'
	}

    def add_root_elements(self, handler):
	super(iTunesFeed, self).add_root_elements(handler)
	handler.addQuickElement('itunes:subtitle', self.feed['subtitle'])
	handler.addQuickElement('itunes:author', self.feed['author_name'])
	handler.addQuickElement('itunes:summary', self.feed['description'])
	handler.startElement('itunes:category', {'text': self.feed['iTunes_category']['text']})
	handler.addQuickElement('itunes:category', '', {'text': self.feed['iTunes_category']['sub']})
	handler.endElement('itunes:category')
	handler.addQuickElement('itunes:explicit',
	       self.feed['iTunes_explicit'])
	handler.startElement("itunes:owner", {})
	handler.addQuickElement('itunes:name', self.feed['iTunes_name'])
	handler.addQuickElement('itunes:email', self.feed['iTunes_email'])
	handler.endElement("itunes:owner")
	handler.addQuickElement('itunes:image', '', {'href': self.feed['iTunes_image_url']})

    def add_item_elements(self, handler, item):
	super(iTunesFeed, self).add_item_elements(handler, item)
	handler.addQuickElement(u'itunes:summary', item['description'])
	handler.addQuickElement(u'itunes:duration', item['duration'])
	handler.addQuickElement(u'itunes:explicit', item['explicit'])


class AtomFeed(MySelectFeed):  
    feed_type = Atom1Feed
    subtitle = MySelectFeed.description


class PodcastHdFeed(AtomFeed):  
    iTunes_explicit = 'clean'
    iTunes_name = settings.TITLE_ETB
    iTunes_email = settings.DEFAULT_FROM_EMAIL
    my_domain = Site.objects.get_current().domain
    iTunes_image_url = 'http://' + my_domain + 'pod_ring.png'
    feed_type = iTunesFeed

    def feed_extra_kwargs(self, obj):
	return {
	    'iTunes_name': self.iTunes_name,
	    'iTunes_email': self.iTunes_email,
	    'iTunes_image_url': self.iTunes_image_url,
	    'iTunes_explicit': self.iTunes_explicit,
	    'iTunes_category': {'text' : 'Education', 'sub' : 'Higher Education'}
	}

    def item_extra_kwargs(self, item):
	return {
	    'summary': item.description,
	    'duration': item.duration_in_time(),
	    'explicit': 'clean',
	 }

    def item_enclosure_url(self, item):
        link = reverse('pods.views.video', args=(item.slug,))
        ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmax = ENCODINGS.aggregate(Max('encodingType__output_height'))['encodingType__output_height__max']
	link = 'http://' + self.current_site.domain + link + "?action=download&resolution=" + str(resolmax)
	#link = 'http://' + str(get_current_site(self.request).domain) + str(ENCODINGS.filter(encodingType__output_height = resolmax)[0].encodingFile)
	print link
	return link 

    def item_enclosure_length(self, item):
	ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmax = ENCODINGS.aggregate(Max('encodingType__output_height'))['encodingType__output_height__max']
	return File(ENCODINGS.filter(encodingType__output_height = resolmax)[0].encodingFile).size

    def item_enclosure_mime_type(self, item):
        return 'video/mp4'

    def item_author(self, item):
        return item.owner.get_full_name() 


class PodcastSdFeed(PodcastHdFeed):

    def item_enclosure_url(self, item):
        link = reverse('pods.views.video', args=(item.slug,))
        ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmin = ENCODINGS.aggregate(Min('encodingType__output_height'))['encodingType__output_height__min']
	link = 'http://' + self.current_site.domain + link + "?action=download&resolution=" + str(resolmin)
	return link 

    def item_enclosure_length(self, item):
	ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmin = ENCODINGS.aggregate(Min('encodingType__output_height'))['encodingType__output_height__min']
	return File(ENCODINGS.filter(encodingType__output_height = resolmin)[0].encodingFile).size


class AudiocastFeed(PodcastHdFeed):

    def item_enclosure_url(self, item):
        link = reverse('pods.views.video', args=(item.slug,))
        ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "audio/mp3")
	print ENCODINGS
	link = 'http://' + self.current_site.domain + link + "?action=download&resolution="
	return link 

    def item_enclosure_length(self, item):
	ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "audio/mp3")
	return File(ENCODINGS[0].encodingFile).size

    def item_enclosure_mime_type(self, item):
        return 'audio/mp3'


class MySelectPodVideoHd(MySelectFeed):
    title = "Test de la fonction RSS"
    link = "/rss/"
    description = "Test feed RSS."

    def item_link(self, item):
        link = reverse('pods.views.video', args=(item.slug,))
        ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmax = ENCODINGS.aggregate(Max('encodingType__output_height'))['encodingType__output_height__max']
	link = link + "?action=download&resolution=" + str(resolmax)
	return link


class MySelectPodVideoSd(MySelectFeed):
    title = "Test de la fonction RSS"
    link = "/rss/"
    description = "Test feed RSS."

    def item_link(self, item):
        link = reverse('pods.views.video', args=(item.slug,))
        ENCODINGS = EncodingPods.objects.filter(video=Pod.objects.get(slug=item.slug), encodingFormat = "video/mp4")
	resolmin = ENCODINGS.aggregate(Min('encodingType__output_height'))['encodingType__output_height__min']
	link = link + "?action=download&resolution=" + str(resolmin)
	return link

