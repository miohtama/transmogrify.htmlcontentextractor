.. contents :: :local:

Introduction
------------

*transmogrify.htmlcontentextractor* is 
collective.tansmogrify blueprint plug-in to extracts out title, description and body 
from HTML either via XPath or by automatic cluster analysis

HTML can be any incoming HTML page. XPath rules or heurestics are used to extract sematic
elements out of it.

Usage
-----

Template finder will associate groups take groups of xpaths and try to extract
field information using them. If any xpath fails for a given group then none of the
extracted text in that group is used and the next xpath is tried. The last group to
be tried is an automatic group made up of xpaths analysed by clustering the pages
Format for options is

Options
=======

Each options consist of

[priority]-[fieldname] = [format] [extraction XPath expression] [Clearing XPath expression] [flags]

* priority-fieldname pair
        
        * *priority* is an integer number starting from 1. If any of field matches
          fail for one priority, htmlcontentextractor will try the next priority group.
        
        * *fieldname* is the name of the sematic schema field which will
          contain the extracted text.  Usually it is: ``text``, ``title`` or ``description`.
        
* *format* is ``text`` or ``html``. lxml is used to flatten the resulting nodes if ``text`
  format is chosen. 

* *Extraction path expression* - if this path is succesfully matched the content is extracted,
  first priority option first. If the extraction path is matched the item is automatically
  removed from the payload HTML.

* *Clearing path expression* **optional** - if the extration path is succesfully matched, these elements
  will be removed from the payload HTML, besides the actual extraction path match. 
  This is useful e.g. when you take description text
  out of the content and you do not want the description decoration labels in the outgoing HTML.

* *Flags* (**optional**) are comma separared text string hints regarding how this field should be regarded. 
   Currently supported flags are
   
        * *soft*: this field does not necessary appear in the input HTML. If the 
          field is missing the other extractors should still complete normally
          and the field value is set to None.
          
.. warning ::

        Due to how syntax is structured, spaces are not allowed inside XPath expressions 

Example in *pipeline.cfg*::

        #
        # Extract title, description and content text from Sphinx generated HTML page
        #
        # Title is the first <h1> element
        #
        # Description is reST "admonition" with name Description 
        #
        # Text is what is left to <body> after removing title and description 
        #
        # Note that spaces in XPaths must be escaped as &#32;
        #
        [templatefinder]
        blueprint = transmogrify.htmlcontentextractor
        auto=False
        1-title = text //div[@class='body']//h1[1]
        1-permalink = text //div[@class='body']//a[@class='headerlink']
        1-description = text //div[contains(@class,'admonition-description')]//p[@class='last'] //div[contains(@class,'admonition-description')]  
        1-text = html //div[@class='body']
    
    
Special options
===============

These options are not considered in the content extraction.

auto
+++++

Set to *true* to apply automatic heurestics to extract the field.

blueprint
+++++++++

The name of this blueprint, *transmogrify.htmlcontentextractor*.

Other
-----

XPath tutorials

* http://www.w3schools.com/xpath/default.asp

Use Firebug to test XPath

* http://blog.browsermob.com/2009/04/test-your-selenium-xpath-easily-with-firebug/
    
Authors
-------

In the order of apperance...

* Dylan Jay

* Mikko Ohtamaa mikko@mfabrik.com http://mfabrik.com

