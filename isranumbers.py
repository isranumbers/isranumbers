#!/usr/bin/python
# vim: set fileencoding=utf-8 :
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

_INDEX_NAME = 'data_index'

class ValidateRequestHandler(webapp2.RequestHandler):
    def validate(self, permission):
        user = users.get_current_user()
        logging.info("validate called")
        logging.info(user)
        url = users.create_login_url(self.request.uri)
        logging.info(url)
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            q = UsersList.all()
            q.filter("email =" , user.email())
            q.filter("permission =" , permission)
            for p in q.run():
                return
            self.redirect('/registrationform')

class ValidateBlobstoreUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def validate(self, permission):
        user = users.get_current_user()
        logging.info("validate called")
        logging.info(user)
        url = users.create_login_url(self.request.uri)
        logging.info(url)
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            q = UsersList.all()
            q.filter("email =" , user.email())
            q.filter("permission =" , permission)
            for p in q.run():
                return
            self.redirect('/registrationform')

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
    #expr_list = [search.SortExpression(expression='author', default_value='', direction=search.SortExpression.DESCENDING)]
    sort_opts = search.SortOptions()
    cursor=search.Cursor()
    if self.request.get('cursor'):
        cursor=search.Cursor(web_safe_string=self.request.get('cursor'))
    search_phrase_options = search.QueryOptions(limit=10,cursor=cursor, sort_options=sort_opts,
                                                  returned_fields=['number', 'units', 'year_of_number', 'month_of_number', 'day_of_number', 'series_type' , 'author'],
                                                  snippeted_fields=['description','source'])

    search_phrase_obj = search.Query(query_string=search_phrase, options=search_phrase_options)
    results = search.Index(name=_INDEX_NAME).search(query=search_phrase_obj)
    cursor=results.cursor
    
    if cursor:
        cursor_string=cursor.web_safe_string
    else:
        cursor_string=""
    table_of_results = [document_to_dictionary(result) for result in results]
#origin
    for result in table_of_results:
        result[u'display_date']=display_date_of_number(result)
        if u'series_type' in result:
            result[u'url']="/displayseries?series_id_to_display=" + result[u'doc_id']
        else:
            result[u'url']="/singlenum?single_number=" + result[u'doc_id']
    data_display_order=[u'number',u'units',u'description',u'display_date',u'source',u'author']
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
        'results': table_of_results,
        'number_found' : number_found,
        'data_display_order' : data_display_order,
        'cursor_string' : cursor_string
    }

    template = jinja_environment.get_template('index.html')
    self.response.out.write(template.render(template_values))
        
def display_date_of_number(document_dictionary):
    display_date=""
    if u'day_of_number' in document_dictionary and document_dictionary[u'day_of_number'] != -1:
        display_date+="%d/" % document_dictionary[u'day_of_number']
    if u'month_of_number' in document_dictionary and document_dictionary[u'month_of_number'] != -1:
        display_date+="%d/" % document_dictionary[u'month_of_number']
    if u'year_of_number' in document_dictionary and document_dictionary[u'year_of_number'] != -1:
        display_date+="%d" % document_dictionary[u'year_of_number']
    return display_date

#todo: create a class wuth validation option for the blobstore hanler like we did with the webapp2 request handler
class UploadCsv(ValidateBlobstoreUploadHandler):
  def get(self): 
    self.validate('editor')
    template_values = {
        'upload_url': blobstore.create_upload_url('/upload')
    }
    template = jinja_environment.get_template('insert_file.html')
    self.response.out.write(template.render(template_values))
  def post(self):
    self.validate('editor')
    file_info = self.get_uploads('csv_file')[0]
    key_str = str(file_info.key())
    taskqueue.add(url='/worker',params = {'key_str' : key_str})
    self.redirect('/')

class UploadSeriesXml(ValidateBlobstoreUploadHandler):
  def get(self): 
    self.validate('editor')
    template_values = {
        'upload_url': blobstore.create_upload_url('/uploadseriesxml')
    }
    template = jinja_environment.get_template('insert_file.html')
    self.response.out.write(template.render(template_values))
  def post(self):
    self.validate('editor')
    file_info = self.get_uploads('csv_file')[0]
    key_str = str(file_info.key())
    taskqueue.add(url='/workerseriesxml',params = {'key_str' : key_str})
    self.redirect('/')

class SeriesXmlWorker(webapp2.RequestHandler):
  def post(self):
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
        data_fields=[search.TextField(name='author', value=author),
            search.TextField(name='description', value=description),
            search.TextField(name='labels', value=labels),
            search.TextField(name='series_type',value=series_type)]
        series_id=search.Index(name=_INDEX_NAME).put(search.Document(
            fields=data_fields + [search.TextField(name='list_of_number_ids', value='')]))[0].id
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
        search.Index(name=_INDEX_NAME).put(search.Document(doc_id=series_id ,
            fields=data_fields + [search.TextField(name='list_of_number_ids', value=list_of_number_ids)]))


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


class InsertNumber(ValidateRequestHandler):
  def get(self): 
    self.validate('editor')
    template = jinja_environment.get_template('insert_number.html')
    self.response.out.write(template.render())
  def post(self):
    self.validate('editor')
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
    
class DeleteNumber(ValidateRequestHandler):
  def get(self):
    self.validate('editor')
    template = jinja_environment.get_template('delete_numbers.html')
    self.response.out.write(template.render())
  def post(self):
    self.validate('editor')
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
        dictionary_of_number_to_display = document_to_dictionary(number_to_display)
        dictionary_of_number_to_display[u'display_date']=display_date_of_number(dictionary_of_number_to_display)
        separate_series = dictionary_of_number_to_display[u'contained_in_series'].split()
        list_of_series_description=[]
        for series_id in separate_series :
            series = search.Index(_INDEX_NAME).get(series_id)
            for field in series.fields:
                if field.name == u'description':
                    list_of_series_description.append((series_id, field.value))
        #target
        self.display_number(dictionary_of_number_to_display,list_of_series_description)

    def display_number(self,dictionary_of_number_to_display,list_of_series_description):
        data_display_order_english=[u'description',u'number',u'units',u'display_date',u'source',u'author', u'labels' , u'contained_in_series']
        hebrew_titles=[u'תיאור הנתון', u'המספר' , u'יחידות המדידה' , u'תאריך' , u'המקור' , u'המזין' , u'תגיות' , u'מופיע בסדרות']
        data_display_order = zip(data_display_order_english,hebrew_titles)
#dealing with hebrew
        template_values = {'dictionary_of_number_to_display' : dictionary_of_number_to_display , 'data_display_order' : data_display_order , 'list_of_series_description' : list_of_series_description}
        template = jinja_environment.get_template('single_number.html')
        self.response.out.write(template.render(template_values))
# ToDo: make list of series show abbrev series description and make sure it works when one number belongs to multiple series


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
    
class InsertSeries(ValidateRequestHandler):
  def get(self): 
    self.validate('editor')
    template = jinja_environment.get_template('insert_series.html')
    self.response.out.write(template.render())
  def post(self):
    self.validate('editor')
    series_id = add_to_series_index(get_author(),
                                    self.request.get('description'),
                                    self.request.get('labels'),
			                        self.request.get('series_type'))
    self.redirect('/addnumbertoseries?series_id=%s' %series_id)

# we should change the optiones to get to this class. on 22.12.2013 the option to get to the handler from the display series page is fine but it can't be accessed from the tool bar. one option is to cancel the option to get to the handler from the tool bar. another option is to deal with the case of directing to this handler without series id by opening a search for series , then select the series we want and than display it in the proper way
class AddNumberToSeries(ValidateRequestHandler):
    def get(self): 
        self.validate('editor')
        if self.request.get('search_phrase'):
            search_phrase=self.request.get('search_phrase')
        else:
            search_phrase=""
# the following commands create the web page shown when AddNumberToSeries is called from the menu bar (without series id)
        if not self.request.get('series_id'):
# the following line should be changed for a better solution to get only results that are series amd not numbers
            search_phrase+=" " + "series"
            sort_opts = search.SortOptions()
# we should consider adding source to the series data
            search_phrase_options = search.QueryOptions(limit=10, sort_options=sort_opts,
                                                          returned_fields=['series_type'],
                                                          snippeted_fields=['description','source'])

            search_phrase_obj = search.Query(query_string=search_phrase, options=search_phrase_options)
            results = search.Index(name=_INDEX_NAME).search(query=search_phrase_obj)

            template_values = {
                                'search_phrase': search_phrase,
                                'results': results,
            }
            template = jinja_environment.get_template('choose_series.html')
            self.response.out.write(template.render(template_values))
# the following commands create the web page when AddNumberToSeries is called with series id
        else:
            series_id = self.request.get('series_id')
            series = search.Index(name=_INDEX_NAME).get(series_id)
            for field in series.fields:
                if field.name == "description" :
                    description = field.value
                if field.name == "labels":    
                    labels = field.value
                if field.name == "series_type" :
                    series_type = field.value


            sort_opts = search.SortOptions()
            search_phrase_options = search.QueryOptions(limit=10, sort_options=sort_opts,
                                                          returned_fields=['number', 'units', 'year_of_number', 'month_of_number', 'day_of_number'],
                                                          snippeted_fields=['description','source'])

            search_phrase_obj = search.Query(query_string=search_phrase, options=search_phrase_options)
            results = search.Index(name=_INDEX_NAME).search(query=search_phrase_obj)

            template_values = { 'series_id' : series_id , 
                                'description' : description ,
                                'labels' : labels , 
                                'series_type' : series_type , 
                                'search_phrase' : search_phrase ,
                                'results' : results}
            template = jinja_environment.get_template('add_number_to_series.html')
            self.response.out.write(template.render(template_values))
    def post(self):
#       add_number_to_series(unicode(self.request.get('number_id')),
#                         unicode(self.request.get('series_id')))
        self.validate('editor')
        add_numbers_to_series(self.request.get('series_id'),self.request.get_all('numbers_in_series'))
        self.redirect('/')

def add_to_series_index(author,description,labels,series_type):
  putresult=search.Index(name=_INDEX_NAME).put(search.Document(
    fields=[search.TextField(name='author', value=author),
            search.TextField(name='list_of_number_ids', value=''),
            search.TextField(name='description', value=description),
            search.TextField(name='labels', value=labels),
	    search.TextField(name='series_type',value=series_type)]))
  logging.info("put result is")
  logging.info(putresult[0].id)
  return putresult[0].id

def add_number_to_series(number_id,series_id):
  logging.info(series_id)
  series=search.Index(name=_INDEX_NAME).get(series_id)
  logging.info( "Series is:")
  logging.info(series)

  updated_fields = []
  for field in series.fields:
      if field.name == u'list_of_number_ids' and string.find(field.value,number_id) == -1:
        updated_fields.append(search.TextField(name=field.name,
                                                 value=field.value + u' ' + number_id))
      else:
        updated_fields.append(field)
  search.Index(name=_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = series_id))
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
      self.display_series(series_id_to_display)
    def display_series(self, series_id_to_display):
        series_to_display_dictionary = document_to_dictionary(search.Index(_INDEX_NAME).get(series_id_to_display))
        number_ids_in_series=series_to_display_dictionary[u'list_of_number_ids'].split()
        series_description=series_to_display_dictionary[u'description']
        series_type=series_to_display_dictionary[u'series_type']
        series_labels=series_to_display_dictionary[u'labels'].split()
        criteria_name = ''
        if series_type == "pie series":
            criteria_name=next(label.replace(u'criteria:', u'' , 1) for label in series_labels if label.startswith(u'criteria:'))


# ToDo we stopped here 12/12/2013, we need to get the criteria name from the series labels
        list_of_numbers=[]
        for number_id in number_ids_in_series:
            num_dictionary = document_to_dictionary(search.Index(_INDEX_NAME).get(number_id))
            if series_type == "time series":
                list_of_numbers.append({'number' : num_dictionary[u'number'],
                                        'year' : int(num_dictionary[u'year_of_number']),
                                        'month' : 1 if int(num_dictionary[u'month_of_number']) == -1 else int(num_dictionary[u'month_of_number']),
                                        'day' : 1 if int(num_dictionary[u'day_of_number']) == -1 else int(num_dictionary[u'day_of_number'])})
            if series_type == "pie series":
                labels = num_dictionary[u'labels'].split()
                criteria_value=next(label.replace(criteria_name + u':', u'' , 1) for label in labels if label.startswith(criteria_name + u':'))
                list_of_numbers.append({'number' : num_dictionary[u'number'],
                                        'criteria_value' : criteria_value ,
#the next lines ar added to prevent bug of mising date data in the javascript code - maybe there is a better way to deal with that bug such as catching exception
                                        'year' : int(num_dictionary[u'year_of_number']),
                                        'month' : 1 if int(num_dictionary[u'month_of_number']) == -1 else int(num_dictionary[u'month_of_number']),
                                        'day' : 1 if int(num_dictionary[u'day_of_number']) == -1 else int(num_dictionary[u'day_of_number'])})
#end of the addition to solve the javascript bug 
        if series_type == "time series":
            list_of_numbers = sorted(list_of_numbers, key=lambda k: (k['year'],k['month'],k['day']))
        if series_type == "pie series":
            list_of_numbers = sorted(list_of_numbers, key=lambda k: k['number'])


        data_display_order_english=[u'description',u'series_type',u'labels',u'source',u'author']
        hebrew_titles=[u'תיאור הסדרה' , u'סוג הסדרה' , u'תגיות' , u'המקור' , u'המזין']
        data_display_order = zip(data_display_order_english,hebrew_titles)

        template_values =  {'series_to_display_dictionary' : series_to_display_dictionary,
                            'data_display_order' : data_display_order,
                            'list_of_numbers' : list_of_numbers,
                            'series_description' : series_description,
#if te series is empty (without numbers) it can't be displayed since there is no default value to "num_dictionary[u'units']" - consider adding default value so also empty sries could be displayed (i think it make some sense that numbers will be added to the data base and then to the series by the user only after he created the series. alternativly we can consider not to let an empty series to be created - and only allow the series to be created after at list one number is added.
                            'units' : num_dictionary[u'units'],
		            	    'series_type' : series_type,
                            'series_id_to_display' : series_id_to_display,
                            'criteria' : criteria_name}
        #deside wether to pass to jinja all the series dictionary or just the relevant data
        template = jinja_environment.get_template('single_series.html')
        self.response.out.write(template.render(template_values))
        # ToDo: add links to numbers.


def document_to_dictionary(document):
    document_dictionary = {u'doc_id' : document.doc_id}
    for field in document.fields:
        document_dictionary[field.name] = field.value
    if hasattr(document,'expressions'):
        for expression in document.expressions:
            document_dictionary[expression.name]=expression.value
    return document_dictionary    

#new function written on january 13 - need to debug before usage - intended to simplify and shorten the code
#fields to change is a dictionary of field names we want to change in the document and their new values 
def change_document_fields(document,fields_to_change):
    fields_to_change_names = []
    for field_name_to_change in fields_to_change:
        fields_to_change_names.append(field_name_to_change)
    updeted_fields=[]
    for field in document.fields:
        if field.name in fields_to_change_names:
            updated_fields.append(search.TextField(name=field.name, value=fields_to_change[field.name]))
        else:
            updated_fields.append(field)
    search.Index(_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = document.doc_id))

def add_numbers_to_series(series_id,numbers_list_of_ids):
    string_of_number_ids=u''
    series = search.Index(name=_INDEX_NAME).get(series_id)
    for number_id in numbers_list_of_ids:
        string_of_number_ids+=u' ' + number_id
#should we check if number_id already exists in list_of_number_ids?        
        number = search.Index(_INDEX_NAME).get(number_id)
        updated_fields = []
        for field in number.fields:
            if field.name != u"contained_in_series":
                updated_fields.append(field)
            else:
                updated_fields.append(search.TextField(name=field.name, value=field.value + u' ' + series_id))
#should we need to take care of a case where "contained_in_series" field does not exist in number?
        search.Index(_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = number_id))
    updated_fields = []
    for field in series.fields:
        if field.name != u'list_of_number_ids':
            updated_fields.append(field)
        else:
            updated_fields.append(search.TextField(name=field.name, value=field.value + u' ' + string_of_number_ids))
    search.Index(_INDEX_NAME).put(search.Document(fields=updated_fields, doc_id = series_id))

class UsersList(db.Model):
  """Models an individual User and its authentications."""
  nickname = db.StringProperty(multiline = True)
  email = db.EmailProperty()
  permission = db.StringProperty()
  active_since = db.DateTimeProperty(auto_now_add=True)
 
# when surfing to a restricted page:
# the Handler should:
# 1. get the current user email (if it doesnt exist - redirect to login page).
# 2. find the relevant user in the database. if it doesn't exist - redirect to a page saying the user doesn't have privileges and letting him submit a form asking for preveleges.
# 3. proceed with the page.

class AuthenticationManagement(webapp2.RequestHandler):
    def get(self):
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login' 
    
        template_values = {
            'url': url,
            'url_linktext': url_linktext
            }
        template = jinja_environment.get_template('authentication.html')
        self.response.out.write(template.render(template_values))

class AdminManagementPage(webapp2.RequestHandler):
    def get(self):
        template_values = { 'register_url' : '/authenticationmanagement/admin/registeruser',
                            'unregister_url' : '/authenticationmanagement/admin/unregisteruser',
                            'display_url' : '/authenticationmanagement/admin/displayuserslist'}
        template = jinja_environment.get_template('authentication_management.html')
        self.response.out.write(template.render(template_values))

class EditorsManagementPage(ValidateRequestHandler):
    def get(self):
        self.validate('editor')
        template_values = { 'register_url' : '/authenticationmanagement/editors/registeruser',
                            'unregister_url' : '/authenticationmanagement/editors/unregisteruser',
                            'display_url' : '/authenticationmanagement/editors/displayuserslist'}
        template = jinja_environment.get_template('authentication_management.html')
        self.response.out.write(template.render(template_values))

#this class will be available only for the admin using the appengine built in admin validation for the link
#we should add a check so there will be no case for 2 users with same nickname
class AdminRegisterUser(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = { 'users' : users ,
                            'register_url' : '/authenticationmanagement/admin/registeruser'}
        template = jinja_environment.get_template('register_user.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        user = UsersList(email=self.request.get("email"))
        q = UsersList.all()
        q.filter("email =" , self.request.get("email"))
        for p in q.run():
            user = p
        user.permission=self.request.get("permission")
        user.nickname=self.request.get("nickname")
        user.put()
        self.redirect('/authenticationmanagement/admin/displayuserslist')

class AdminUnregisterUser(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = { 'users' : users ,
                            'unregister_url' : '/authenticationmanagement/admin/unregisteruser'}
        template = jinja_environment.get_template('unregister_user.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        q = UsersList.all()
        q.filter("nickname =" , self.request.get("nickname"))
        for p in q.run():
            p.delete()
        self.redirect('/authenticationmanagement/admin/displayuserslist')

#avilable only to admin
class AdminDisplayUsersList(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = {'users' : users}
        template = jinja_environment.get_template('display_users_list.html')
        self.response.out.write(template.render(template_values))

class EditorsRegisterUser(ValidateRequestHandler):
    def get(self):
        self.validate('editor')
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = { 'users' : users ,
                            'register_url' : '/authenticationmanagement/editors/registeruser'}
        template = jinja_environment.get_template('register_user.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        self.validate('editor')
        user = UsersList(email=self.request.get("email"))
        q = UsersList.all()
        q.filter("email =" , self.request.get("email"))
        for p in q.run():
            user = p
        user.permission=self.request.get("permission")
        user.nickname=self.request.get("nickname")
        user.put()
        self.redirect('/authenticationmanagement/editors/displayuserslist')

class EditorsUnregisterUser(ValidateRequestHandler):
    def get(self):
        self.validate('editor')
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = { 'users' : users ,
                            'unregister_url' : '/authenticationmanagement/editors/unregisteruser'}
        template = jinja_environment.get_template('unregister_user.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        self.validate('editor')
        q = UsersList.all()
        q.filter("nickname =" , self.request.get("nickname"))
        for p in q.run():
            p.delete()
        self.redirect('/authenticationmanagement/editors/displayuserslist')

class EditorsDisplayUsersList(ValidateRequestHandler):
    def get(self):
        self.validate('editor')
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = {'users' : users}
        template = jinja_environment.get_template('display_users_list.html')
        self.response.out.write(template.render(template_values))

class RegistrationForm(webapp2.RequestHandler):
    def get(self):
        template = jinja_environment.get_template('registration_form.html')
        self.response.out.write(template.render())

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
                               ('/displayseries', DisplaySeries),
                               ('/authenticationmanagement', AuthenticationManagement),
                               ('/authenticationmanagement/editors', EditorsManagementPage),
                               ('/authenticationmanagement/editors/registeruser',EditorsRegisterUser),
                               ('/authenticationmanagement/editors/unregisteruser',EditorsUnregisterUser),
                               ('/authenticationmanagement/editors/displayuserslist',EditorsDisplayUsersList),
                               ('/authenticationmanagement/admin', AdminManagementPage),
                               ('/authenticationmanagement/admin/registeruser',AdminRegisterUser),
                               ('/authenticationmanagement/admin/unregisteruser',AdminUnregisterUser),
                               ('/authenticationmanagement/admin/displayuserslist',AdminDisplayUsersList),
                               ('/registrationform',RegistrationForm)],
                              debug=True)

