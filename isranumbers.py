import cgi
import datetime
import urllib
import webapp2
import jinja2
import os

from google.appengine.ext import db
from google.appengine.api import users

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


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
    # Ancestor Queries, as shown here, are strongly consistent with the High
    # Replication Datastore. Queries that span entity groups are eventually
    # consistent. If we omitted the ancestor from this query there would be a
    # slight chance that greeting that had just been written would not show up
    # in a query.
    numbers = IsraNumber.gql("WHERE ANCESTOR IS :1 LIMIT 10", isra_key())
    
    if users.get_current_user():
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'
    else:
        url = users.create_login_url(self.request.uri)
        url_linktext = 'Login' 
    
    template_values = {
        'numbers': numbers,
        'url': url,
        'url_linktext': url_linktext,
    }

    template = jinja_environment.get_template('index.html')
    self.response.out.write(template.render(template_values))
    


class InsertNumber(webapp2.RequestHandler):
  def post(self):
    number = IsraNumber(parent=isra_key())

    if users.get_current_user():
      number.author = users.get_current_user().nickname()

    number.number = float(self.request.get('number'))
    number.units = self.request.get('units')
    number.description = self.request.get('description')
    number.labels = self.request.get('labels')
    number.source = self.request.get('source')
    number.year_of_number = int(self.request.get('year_of_number'))
    number.month_of_number = int(self.request.get('month_of_number'))
    number.day_of_number = int(self.request.get('day_of_number'))
    number.put()
    self.redirect('/')


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/sign', InsertNumber)],
                              debug=True)

