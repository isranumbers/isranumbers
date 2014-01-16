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
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        q = UsersList.all()
        q.filter("email =" , user.email())
        q.filter("permission =" , permission)
        for p in q.run():
            return
        self.redirect('/registerform')


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
    search_phrase_options = search.QueryOptions(limit=10, sort_options=sort_opts,
                                                  returned_fields=['number', 'units', 'year_of_number', 'month_of_number', 'day_of_number', 'series_type'],
                                                  snippeted_fields=['description','source'])

    search_phrase_obj = search.Query(query_string=search_phrase, options=search_phrase_options)
    results = search.Index(name=_INDEX_NAME).search(query=search_phrase_obj)
    logging.info(results)
    
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
        for field in number_to_display.fields:
            if field.name == u'contained_in_series':
                seperate_series = field.value.split()
        list_of_series_description=[]
        for series_id in seperate_series :
            series = search.Index(_INDEX_NAME).get(series_id)
            for field in series.fields:
                if field.name == u'description':
                    list_of_series_description.append((series_id, field.value))
        self.display_number(number_to_display,list_of_series_description,doc_id_to_display)

    def display_number(self,number_to_display,list_of_series_description,doc_id_to_display):
        template_values = {'number_to_display' : number_to_display , 'list_of_series_description' : list_of_series_description , 'doc_id_to_display' : doc_id_to_display}
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
    
class InsertSeries(webapp2.RequestHandler):
  def get(self): 
    logging.info("getting")
    template = jinja_environment.get_template('insert_series.html')
    self.response.out.write(template.render())
  def post(self):
    logging.info("posting")
    series_id = add_to_series_index(get_author(),
                                    self.request.get('description'),
                                    self.request.get('labels'),
			                        self.request.get('series_type'))
    self.redirect('/addnumbertoseries?series_id=%s' %series_id)

# we should change the optiones to get to this class. on 22.12.2013 the option to get to the handler from the display series page is fine but it can't be accessed from the tool bar. one option is to cancel the option to get to the handler from the tool bar. another option is to deal with the case of directing to this handler without series id by opening a search for series , then select the series we want and than display it in the proper way
class AddNumberToSeries(webapp2.RequestHandler):
  def get(self): 
    if self.request.get('search_phrase'):
      search_phrase=self.request.get('search_phrase')
    else:
      search_phrase=""
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

    template_values = {'series_id' : series_id , 
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
        template_values =  {'series_to_display_dictionary' : series_to_display_dictionary,
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
        template = jinja_environment.get_template('authentication_management.html')
        self.response.out.write(template.render())

#this class will be available only for the admin using the appengine built in admin validation for the link
#we should add a check so there will be no case for 2 users with same nickname
class RegisterUser(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = {'users' : users}
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
        self.redirect('/authenticationmanagement/displayuserslist')

class UnregisterUser(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = {'users' : users}
        template = jinja_environment.get_template('unregister_user.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        q = UsersList.all()
        q.filter("nickname =" , self.request.get("nickname"))
        for p in q.run():
            p.delete()
        self.redirect('/authenticationmanagement/displayuserslist')

#avilable only to admin
class DisplayUsersList(webapp2.RequestHandler):
    def get(self):
        q=UsersList.all()
        users = []
        for user in q.run():
            users.append(user)
        template_values = {'users' : users}
        template = jinja_environment.get_template('display_users_list.html')
        self.response.out.write(template.render(template_values))

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
                               ('/authenticationmanagement/registeruser',RegisterUser),
                               ('/authenticationmanagement/unregisteruser',UnregisterUser),
                               ('/authenticationmanagement/displayuserslist',DisplayUsersList)],
                              debug=True)

