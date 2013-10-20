import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import string
import csv
import logging
import xml.etree.cElementTree as ET

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import search
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

_INDEX_NAME = 'allnumbers'
_SERIES_INDEX_NAME = 'allseries'

class IsraNumber(db.Model):
  """Models an individual IsraNumber entry with an author, number, 
  units, and description."""
  author = db.StringProperty()
  insertion_time= db.DateTimeProperty(auto_now_add=True)
  number = db.FloatProperty()
  units = db.StringProperty()
  labels = db.StringProperty(multiline = True)
  description = db.StringProperty(multiline = True)
  source = db.StringProperty()
  year_of_number = db.IntegerProperty()
  month_of_number =db.IntegerProperty()
  day_of_number =db.IntegerProperty()
  

def isra_key():
  return db.Key.from_path('IsraBook','IsraTable')


class MainPage(webapp2.RequestHandler):
  def get(self):
    #get the number of entries in the index
    default_options = search.QueryOptions(limit=1)
    empty_search_phrase_obj = search.Query(query_string="",options=default_options)
    results_for_number_of_data_documents=search.Index(name=_INDEX_NAME).search(query=empty_search_phrase_obj)
    number_found = results_for_number_of_data_documents.number_found
    if self.request.get('search_phrase'):
      search_phrase=self.request.get('search_phrase')
    else:
      search_phrase=""
    #need to check if the scoredDocunemt istances are set to hebrew automatically
    #and also if the different fields can be in different language
    expr_list = [search.SortExpression(expression='author', default_value='', direction=search.SortExpression.DESCENDING)]
    sort_opts = search.SortOptions(expressions=expr_list)
    search_phrase_options = search.QueryOptions(limit=10, sort_options=sort_opts,
                                                  returned_fields=['author', 'number', 'units', 'description'])
    search_phrase_obj = search.Query(query_string=search_phrase, options=search_phrase_options)
    results = search.Index(name=_INDEX_NAME).search(query=search_phrase_obj)
#ToDo consider searching both in the number and series indices and return results for numbers and series

    
    if users.get_current_user():
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'
    else:
        url = users.create_login_url(self.request.uri)
        url_linktext = 'Login' 
    
    template_values = {
        'url': url,
        'url_linktext': url_linktext,
        'search_phrase': search_phrase,
        'results': results,
        'number_found' : number_found,
    }

    template = jinja_environment.get_template('index.html')
    self.response.out.write(template.render(template_values))
        
class UploadCsv(blobstore_handlers.BlobstoreUploadHandler):
  def get(self): 
    template_values = {
        'upload_url': blobstore.create_upload_url('/upload')
    }
    template = jinja_environment.get_template('insert_file.html')
    self.response.out.write(template.render(template_values))
  def post(self):
    file_info = self.get_uploads('csv_file')[0]
    key_str = str(file_info.key())
    taskqueue.add(url='/worker',params = {'key_str' : key_str})
    self.redirect('/')

class UploadSeriesXml(blobstore_handlers.BlobstoreUploadHandler):
  def get(self): 
    template_values = {
        'upload_url': blobstore.create_upload_url('/uploadseriesxml')
    }
    template = jinja_environment.get_template('insert_file.html')
    self.response.out.write(template.render(template_values))
  def post(self):
    file_info = self.get_uploads('csv_file')[0]
    key_str = str(file_info.key())
    taskqueue.add(url='/workerseriesxml',params = {'key_str' : key_str})
    self.redirect('/')

class SeriesXmlWorker(webapp2.RequestHandler):
  def post(self):
    logging.info("worker called")
    file_info = blobstore.BlobInfo(blobstore.BlobKey(self.request.get('key_str')))
    reader = blobstore.BlobReader(file_info)
    tree = ET.parse(reader)
    root = tree.getroot()
    author=get_author()
    for child in root:
        list_of_number_ids=u''
        description=child.attrib['description']
        labels=child.attrib['labels']
	series_type=child.attrib['series_type']
        units=child.attrib['unit']
	source=child.attrib['source']
        logging.info(description)
	data_fields=[search.TextField(name='author', value=author),
            search.TextField(name='description', value=description),
            search.TextField(name='labels', value=labels),
	    search.TextField(name='series_type',value=series_type)]
        series_id=search.Index(name=_SERIES_INDEX_NAME).put(search.Document(
    	    fields=data_fields + [search.TextField(name='list_of_number_ids', value='')]))[0].id
	logging.info(series_id)
	for number in child:
	    value=float(number.attrib['value'])
	    year='-1'
	    month='-1'
	    day='-1'
	    time=number.attrib['time_period']
            if time.find('-') != -1:
                year = time.split('-')[0]
                month = time.split('-')[1]
		if len(time.split('-'))==3:
		    day = time.split('-')[2] 
   	    else:
		year=time
	    number_id=search.Index(name=_INDEX_NAME).put(search.Document(
    	      fields=[search.TextField(name='author', value=author),
              search.NumberField(name='number', value=value),
              search.TextField(name='units', value=units),
              search.TextField(name='description', value=description),
              search.TextField(name='labels', value=labels),
              search.TextField(name='source', value=source),
              search.NumberField(name='year_of_number', value=int(year)),
              search.NumberField(name='month_of_number', value=int(month)),
              search.NumberField(name='day_of_number', value=int(day)),
	      search.TextField(name='contained_in_series', value=series_id)]))[0].id
            list_of_number_ids+=u" " + number_id
  	    search.Index(name=_SERIES_INDEX_NAME).put(search.Document(fields=data_fields, doc_id = series_id))
        search.Index(name=_SERIES_INDEX_NAME).put(search.Document(doc_id=series_id ,
    	    fields=data_fields + [search.TextField(name='list_of_number_ids', value=list_of_number_ids)]))

   #we stopped here     
    

class CsvWorker(webapp2.RequestHandler):
  def post(self):
    logging.info("worker called")
    file_info = blobstore.BlobInfo(blobstore.BlobKey(self.request.get('key_str')))
    reader = blobstore.BlobReader(file_info)
    next(reader)
    csv_file_content= csv.reader(reader, delimiter=',', quotechar='"')   
    
    for row in csv_file_content:      
      add_to_number_index(get_author(),          
                          float(row[0]),
                          row[1],
                          row[2],
                          row[3],
                          row[4],
                          int(row[5]),
                          int(row[6]),
                          int(row[7]))
    logging.info("worker finished")


class InsertNumber(webapp2.RequestHandler):
  def get(self): 
    template = jinja_environment.get_template('insert_number.html')
    self.response.out.write(template.render())
  def post(self):
    add_to_number_index(get_author(),
                        float(self.request.get('number')),
                        self.request.get('units'),
                        self.request.get('description'),
                        self.request.get('labels'),
                        self.request.get('source'),
                        int(self.request.get('year_of_number')),
                        int(self.request.get('month_of_number')),
                        int(self.request.get('day_of_number')))     
              
    self.redirect('/')
    
class DeleteNumber(webapp2.RequestHandler):
  def get(self):
    template = jinja_environment.get_template('delete_numbers.html')
    self.response.out.write(template.render())
  def post(self):
    documents_to_delete = int(self.request.get('documents_to_delete'))
    doc_index = search.Index(name=_INDEX_NAME)
    for i in range(0,documents_to_delete):    
      document_ids = [document.doc_id
                      for document in doc_index.get_range(limit=200 , ids_only=True)]
      if document_ids:    
        doc_index.delete(document_ids)
    self.redirect('/')


class SingleNumber(webapp2.RequestHandler):
    def get(self):
        doc_id_to_display = self.request.get('single_number')
        number_to_display = search.Index(_INDEX_NAME).get(doc_id_to_display)
#begin new part 17.10.2013
        for field in number_to_display.fields:
            if field.name == u'contained_in_series':
                seperate_series = field.value.split()
        list_of_series_description=[]
        for series_id in seperate_series :
            series = search.Index(_SERIES_INDEX_NAME).get(series_id)
            for field in series.fields:
                if field.name == u'description':
                    list_of_series_description.append((series_id, field.value))
#        for field in number_to_display.fields:
#            if field.name == u'contained_in_series':
 #               field.value = list_of_series_description
#untill here new part 17.10.2013
        self.display_number(number_to_display,list_of_series_description)

    def display_number(self,number_to_display,list_of_series_description):
        template_values = {'number_to_display' : number_to_display , 'list_of_series_description' : list_of_series_description}
        template = jinja_environment.get_template('single_number.html')
        self.response.out.write(template.render(template_values))
# ToDo: make list of series show abbrev series description and link to series page.


def get_author():
  author = "None"
  if users.get_current_user():
    author = users.get_current_user().nickname().split('@')[0]
  return author  


def add_to_number_index(author,number,units,description,labels,source,year,month,day):
  x = search.Index(name=_INDEX_NAME).put(search.Document(
    fields=[search.TextField(name='author', value=author),
              search.NumberField(name='number', value=number),
              search.TextField(name='units', value=units),
              search.TextField(name='description', value=description),
              search.TextField(name='labels', value=labels),
              search.TextField(name='source', value=source),
              search.NumberField(name='year_of_number', value=year),
              search.NumberField(name='month_of_number', value=month),
              search.NumberField(name='day_of_number', value=day),
	      search.TextField(name='contained_in_series', value='')]))
  logging.info(dir(x[0]))
  logging.info(x)
    
class InsertSeries(webapp2.RequestHandler):
  def get(self): 
    logging.info("getting")
    template = jinja_environment.get_template('insert_series.html')
    self.response.out.write(template.render())
  def post(self):
    logging.info("posting")
    add_to_series_index(get_author(),
                        self.request.get('description'),
                        self.request.get('labels'),
			self.request.get('series_type'))
    self.redirect('/')


class AddNumberToSeries(webapp2.RequestHandler):
  def get(self): 
    template = jinja_environment.get_template('add_number_to_series.html')
    self.response.out.write(template.render())
  def post(self):
    add_number_to_series(unicode(self.request.get('number_id')),
                         unicode(self.request.get('series_id')))
    self.redirect('/')

def add_to_series_index(author,description,labels,series_type):
  putresult=search.Index(name=_SERIES_INDEX_NAME).put(search.Document(
    fields=[search.TextField(name='author', value=author),
            search.TextField(name='list_of_number_ids', value=''),
            search.TextField(name='description', value=description),
            search.TextField(name='labels', value=labels),
	    search.TextField(name='series_type',value=series_type)]))
  logging.info("put result is")
  logging.info(putresult)
  return putresult

def add_number_to_series(number_id,series_id):
  logging.info(series_id)
  series=search.Index(name=_SERIES_INDEX_NAME).get(series_id)
  logging.info( "Series is:")
  logging.info(series)

  updated_fields = []
  for field in series.fields:
      if field.name == u'list_of_number_ids' and string.find(field.value,number_id) == -1:
        updated_fields.append(search.TextField(name=field.name,
                                                 value=field.value + u' ' + number_id))
      else:
        updated_fields.append(field)
  search.Index(name=_SERIES_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = series_id))
  number=search.Index(name=_INDEX_NAME).get(number_id)
  updated_fields = []
  for field in number.fields:
      if field.name == u'contained_in_series' and string.find(field.value,series_id) == -1:
        updated_fields.append(search.TextField(name=field.name, value=field.value + u' ' + series_id))
      else:
        updated_fields.append(field)
  search.Index(name=_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = number_id))
   
class DisplaySeries(webapp2.RequestHandler):
    def get(self):
      series_id_to_display = self.request.get('series_id_to_display')
      series_to_display = search.Index(_SERIES_INDEX_NAME).get(series_id_to_display)
      self.display_series(series_to_display)
    def display_series(self, series_to_display):
        for field in series_to_display.fields:
            if field.name == u'list_of_number_ids':
                number_ids_in_series=field.value.split()

            if field.name == u'description':
                series_description=field.value
            if field.name == u'series_type':
		series_type=field.value
	list_of_numbers=[]
        for number_id in number_ids_in_series:
            num = None
            year = None
            month = None
            day = None
            for field in search.Index(_INDEX_NAME).get(number_id).fields:
                if field.name==u'number':
                    num = field.value
                if field.name==u'year_of_number':
                    year = int(field.value)
                if field.name==u'month_of_number':
		    month=int(field.value)
		    if field.value==-1:
		        month=1
                if field.name==u'day_of_number':
                    day=int(field.value)
		    if field.value==-1:
		        day=1
                if field.name==u'units':
                    units=field.value
            list_of_numbers.append({'number' : num,
                                    'year' : year,
                                    'month' : month,
                                    'day' : day})
        sorted_list_of_numbers = sorted(list_of_numbers, key=lambda k: (k['year'],k['month'],k['day']))
        
        template_values = {'series_to_display' : series_to_display,
                            'list_of_numbers' : sorted_list_of_numbers,
                            'series_description' : series_description,
                            'units' : units,
			    'series_type' : series_type}
        template = jinja_environment.get_template('single_series.html')
        self.response.out.write(template.render(template_values))
        # ToDo: add links to numbers.
# ToDo: automatically create time series for LAMAS data.

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/insertnumber', InsertNumber),
                               ('/upload', UploadCsv),
                               ('/uploadseriesxml', UploadSeriesXml),
                               ('/worker', CsvWorker),
                               ('/workerseriesxml', SeriesXmlWorker),
                               ('/delete', DeleteNumber),
                               ('/singlenum', SingleNumber),
                               ('/insertseries', InsertSeries),
                               ('/addnumbertoseries', AddNumberToSeries),
                               ('/displayseries', DisplaySeries)],
                              debug=True)

