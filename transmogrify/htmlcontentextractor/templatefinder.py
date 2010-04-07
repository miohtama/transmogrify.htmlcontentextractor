
import fnmatch
from StringIO import StringIO
from sys import stderr

from zope.interface import classProvides
from zope.interface import implements
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.utils import Matcher

from webstemmer.analyze import PageFeeder, LayoutAnalyzer, LayoutCluster
from webstemmer.extract import TextExtractor, LayoutPatternSet, LayoutPattern
from webstemmer.layoutils import sigchars, get_textblocks, retrieve_blocks, WEBSTEMMER_VERSION, KEY_ATTRS
from webstemmer.zipdb import ACLDB
from webstemmer.htmldom import parse
from lxml import etree
import lxml.html
import lxml.html.soupparser
from lxml.etree import XPathEvalError

#patch LayoutCluster to make it LayoutPattern
def match_blocks(self, blocks0, strict=True):
    diffs = [ d for (d,m,p) in self.pattern ]
    mains = [ m for (d,m,p) in self.pattern ]
    paths = [ p for (d,m,p) in self.pattern ]
    layout = []
    for (diffscore,mainscore,blocks1,path) in zip(diffs, mains, retrieve_blocks(paths, blocks0), paths):
      if strict and not blocks1:
        return None
      layout.append(LayoutSection(len(layout), diffscore, mainscore, blocks1, path))
    return layout
LayoutCluster.match_blocks = match_blocks
LayoutCluster.main_sectno = -1

class LayoutSection:

  def __init__(self, id, diffscore, mainscore, blocks,path):
    self.id = id
    self.diffscore = diffscore
    self.mainscore = mainscore
    self.weight = sum( b.weight for b in blocks )
    self.blocks = blocks
    self.path = path
    return




"""
XPath Tests
===========

We want to take webstemmers patterns and get the actually html rather than just
the text. To do this we will convert a pattern to xpath

    >>> pat = 'div:class=section1/p:align=center:class=msonormal/span'
    >>> xp = toXPath(pat)
    '//div[re:test(@class,"^section1$","i")]/p[re:test(@align,"^center$","i")][re:test(@class,"^msonormal$","i")]/span'

Lets check it gets the right parts of the text

    >>> text = '<div class="Section1">\n\n<p class="MsoNormal" align="center" style="text-align:center"><b style="mso-bidi-font-weight:
 normal"><span lang="EN-AU" style="font-size:20.0pt"/></b></p>\n\n<p class="MsoNormal" align="center" style="text-align:
center"><b style="mso-bidi-font-weight: normal"><span lang="EN-AU" style="font-size:20.0pt">Customer Service Standards</
span></b></p>\n\n<p class="MsoNormal"><span lang="EN-AU"/></p>\n\n<p class="MsoNormal"><span lang="EN-AU"/></p>\n\n<p cl
ass="MsoNormal"><span lang="EN-AU"/></p>\n\n<p class="MsoNormal" style="margin-top:0cm;margin-right:-23.55pt;margin-bott
om: 0cm;margin-left:45.1pt;margin-bottom:.0001pt;text-indent:-27.0pt;mso-pagination: none;mso-list:l2 level1 lfo3;tab-st
ops:list 45.0pt"><b style="mso-bidi-font-weight:normal"><span lang="EN-AU" style="font-size:16.0pt; mso-fareast-font-fam
ily:Arial"><span style="mso-list:Ignore">1.<span style="font:7.0pt "/>Times New Roman""&gt;\n</span></span></b></p><b st
yle="mso-bidi-font-weight:normal"><span lang="EN-AU" style="font-size:16.0pt">Care for the customer and show respect for
\nthem and their property.</span></b></div>'

    >>> parser = etree.XMLParser(recover=True)
    >>> tree = etree.parse(StringIO(text), parser)
    >>> nodes = tree.xpath(xp,namespaces=ns)
    >>> result = etree.tostring(nodes[0])


"""


ns = {'re':"http://exslt.org/regular-expressions"}

import re
attr = re.compile(r':(?P<attr>[^/:]*)=(?P<val>[^/:]*)')
def toXPath(pat):
    #td:valign=top/p:class=msonormal/span
    pat = attr.sub(r'[re:test(@\g<attr>,"^\g<val>$","i")]', pat)
    pat = pat.replace('/', '//')
    return "//" + pat


default_charset='utf-8'

class TemplateFinder(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    """ Template finder will associate groups take groups of xpaths and try to extract
    field information using them. If any xpath fails for a given group then none of the
    extracted text in that group is used and the next xpath is tried. The last group to
    be tried is an automatic group made up of xpaths analysed by clustering the pages
    Format for options is

    1-content = text //div
    2-content = html //div
    1-title = text //h1
    2-title = html //h2
    """



    def __init__(self, transmogrifier, name, options, previous):
        """ Initialize section blueprint.
        
        @param transmogrifier:  collective.transmogrifier.transmogrifier.Transmogrifier instance
        
        @param name: Section name as given in the blueprint
        
        @param previous: Prior blueprint in the chain. A Python generator object.
        
        @param options: Options as a dictionary as they appear in pipeline.cfg. Parsed INI format.
        
        """
        
        self.previous = previous
        self.auto = options.get('auto', True)
        self.auto = self.auto in ['True','true','yes','Y']
        
        # Contains dictionary of nested dictionaries of field look-ups in their match order
        
        # {'1': {'text': [('html', "//div[@class='body']")], 
        #        'permalink': [('text', "//div[@class='body']//a[@class='headerlink']")], 
        #        'description': [('text', "//div[@class='body']/div[@class='section']/p[1]")], 
        #        'title': [('text', "//div[@class='body']//h1[1]")]}, 
        # '3': {'text': [('html', "//div[@class='body']")]}, 
        # '2': ...
        #
        # Each field is tuple of format, extraction path, deletion path
        # 
        self.groups = {}
        for key, value in options.items():
            if key in ['blueprint','auto']:
                continue
            try:
                group, field = key.split('-', 1)
            except:
                group, field = '1',key
            xps = []
            for line in value.strip().split('\n'):
                res = re.findall("^(text |html |)(.*)$", line)
            
                if not res:
                    # does not start with text or html
                    print "Line in invalid format:" + line
                    continue
                else:
                    format,xp = res[0]
                format = format.strip()
                format = format == '' and 'html' or format
                
                # Try get extration and deletion xpath
                # the latter being optional
                parts = xp.split(" ")
                extraction_path = parts[0]
                if len(parts) >= 2:
                    deletion_path = parts[1]
                else:
                    deletion_path = None
                    
                # Make a record 
                xps.append((format, extraction_path, deletion_path))
            
            group = self.groups.setdefault(group, {})
            group[field] = xps
            
            
    def check_and_extract(self, item, content):
        """ Check whether extration XPath applies to the item being tested and then perform the extraction.
                
        @param content: Content HTML as string
        
        @return: True if the field was extracted and the item in the question was added the field value.
        """
        
        path = item['_site_url'] + item['_path']

        gotit = False
        for groupname in sorted(self.groups.keys()):
                group = self.groups[groupname]
                tree = lxml.html.fromstring(content)
                if group.get('path', path) == path and self.extract(group, tree, item):
                    gotit = True
                    break

        return gotit
    
    def __iter__(self):
        """
        Perform the extration.
        
        Yiels item from the previous blueprint output, 
        extractes necessary content, mutates content,
        and passes the item forward.
        """

        # Contains name of the fields for which 
        # we do not get match, and then perform automatic analysation for them
        notextracted = []
        
        # Items are arbitary Python dictionary,
        # which keys must be guessed based from the context
        # this blueprint is run.
        # Available keys in this point
        # ['_type', '_sortorder', '_content_info', '_mimetype', 'text', '_origin', '_backlinks', '_site_url', '_path'] 
        
        # Keys starting with underscore are "hints" what the incoming is 
        # Keys startting without underscore are extracted field values
        for item in self.previous:
            
            # Parse payload of item to LXML tree
            content = self.getHtml(item)
            if content is None:
                # print "No extractable HTML payload for item:" + item["_path"]
                yield item
                continue
            
            
            # try each group in turn to see if they work
            gotit = self.check_and_extract(item, content)
         
            if gotit:
                # Extracting using manual XPath succeed, we are done with the item
                yield item
            else:
                # Put item to auto-analyze queue
                notextracted.append(item)


        if self.auto:
            for item in self.analyse(notextracted):
                yield item
        else:
            for item in notextracted:
                yield item


    def extract(self, pats, tree, item):
        """ Update blueprint pipeline item with extracted field contents.
        
        Extract all fields in this pass.
        
        @param pats: Extraction patters for the current field group as fieldname : format + path record tuples
        
        @param tree: lxml parsed HTML tree as DOM
        
        @param item: Transmogrifier item being mutated
            
        """
        
        # Contains dictionary of field name : (format, payload) pairs
        unique = {}
        
        # List of node obejcts which have matched deletion expression
        to_be_deleted = []
        
        # Each field is pair of name and list of XPath (format, extraction path, deletion path) tuples
        for field, xps in pats.items():
            
            # TODO: No clue what this is
            if field == 'path':
                continue
            
            # Go through all assigned extration patterns for this field
            for format, xp, deletion_xp in xps:
                
                try:
                    nodes = tree.xpath(xp, namespaces=ns)
                except XPathEvalError, e:
                    # Include XPath content in the error, makes debugging
                    # lots of more fun
                    # args = list o exception arguments, containing message
                    e.args = list(e.args) + [u"Bad XPath '%s'" % xp]
                    raise e
                    
                if not nodes:
                    print "TemplateFinder: NOMATCH: %s=%s(%s)" % (field, format, xp)
                    # TODO: bug here?
                    return False
                
                deletion_nodes = None
                if deletion_xp:
                    # Do we have a special deletion XPath for this item
                    deletion_nodes = tree.xpath(deletion_xp, namespaces=ns)
                    if deletion_nodes:
                        to_be_deleted += deletion_nodes
                
                # We might match several nodes per expression
                # Convert field to (format, payload LXML nodes, deletion LXML nodes) record 
                nodes = [(format, n) for n in nodes]
                
                # TODO: DOES NOT UNDERSTAND 
                unique[field] = nonoverlap(unique.setdefault(field,[]), nodes)
                
        extracted = {}
        
        # we will pull selected nodes out of tree so data isn't repeated
        for field, nodes, in unique.items():
            for format, node in nodes:
                node.drop_tree()
                
        for node in to_be_deleted:
            node.drop_tree()
        
        for field, nodes in unique.items():
            for format, node in nodes:
                extracted.setdefault(field,'')
                if format == 'text':
                    extracted[field] += etree.tostring(node, method='text', encoding=unicode) + ' '
                else:
                    extracted[field] += '<div>%s</div>' % etree.tostring(node, method='html', encoding=unicode)
        
        item.update(extracted)
        
        if '_tree' in item:
            del item['_tree']
        
        item['_template'] = None
        
        return item

    def getHtml(self, item):
              path = item.get('_path', None)
              content = item.get('_content', None) or item.get('text', None)
              mimetype = item.get('_mimetype', None)
              if  path is not None and \
                    content is not None and \
                    mimetype in ['text/xhtml', 'text/html']:
                  return content
              else:
                  return None


    def analyse(self, previous):
        """
        Perform automatic field extration without hints.
        
        Deep magic.
        """
        (debug, cluster_threshold, title_threshold, score_threshold) = (0, 0.97, 0.6, 100)
        mangle_pat = None
        linkinfo = 'linkinfo'
        #
        analyzer = LayoutAnalyzer(debug=debug)
        if mangle_pat:
            analyzer.set_encoder(mangle_pat)

        feeder = PageFeeder(analyzer, linkinfo=linkinfo, acldb=None,
                                default_charset=default_charset, debug=debug)

        items = []
        for item in previous:
            content = self.getHtml(item)
            if content is not None:
                feeder.feed_page(item['_site_url'] + item['_path'], content)
                items.append(item)
            else:
                yield item
            feeder.close()

        self.clusters = {}
        clusters = analyzer.analyze(cluster_threshold, title_threshold)
        patternset = LayoutPatternSet()
        patternset.pats = [c for c in clusters if c.pattern and score_threshold <= c.score]

        #default_charset='iso-8859-1'
        pat_threshold=0.8
        self.debug = 0
        strict=True
        for item in items:
            content = self.getHtml(item)
            name = item['_site_url'] + item['_path']
            if name == 'linkinfo': continue
            tree = parse(content, charset=default_charset)
            (pat1, layout) = patternset.identify_layout(tree, pat_threshold, strict=strict)
            etree = lxml.html.fromstring(content)
            item.update( self.dump_text(name, pat1, layout, etree) )
            yield item


    def dump_text(self, name, pat1, layout, tree):
        codec_out='utf-8'
        diffscore_threshold=0.5
        main_threshold=50

        item = {}

        enc = lambda x: x.encode(codec_out, 'replace')
        if not layout:
          print '!UNMATCHED: %s' % name
        else:
          print '!MATCHED: %s' % name
          print 'PATTERN: %s' % pat1.name
          if self.debug:
            for sect in layout:
              print >>stderr, 'DEBUG: SECT-%d: diffscore=%.2f' % (sect.id, sect.diffscore)
              for b in sect.blocks:
                print >>stderr, '   %s' % enc(b.orig_text)


          for sectno in xrange(len(layout)):
            sect = layout[sectno]
            field = None
            if sectno == pat1.title_sectno:
              field = 'title'
              for b in sect.blocks:
                print 'TITLE: %s' % enc(b.orig_text)

            elif diffscore_threshold <= sect.diffscore:
              if pat1.title_sectno < sectno and main_threshold <= sect.mainscore:
                field = 'text'
                for b in sect.blocks:
                  print 'MAIN-%d: %s' % (sect.id, enc(b.orig_text))
              else:
                field = 'text'
                for b in sect.blocks:
                  print 'SUB-%d: %s' % (sect.id, enc(b.orig_text))

              if field:
                  for node in tree.xpath(toXPath(sect.path), namespaces=ns):
                      item.setdefault(field,'')
                      method = field == 'title' and 'text' or 'html'
                      item[field] += etree.tostring(node, method=method, encoding=unicode) + ' '
                      


        print
        return item


def nonoverlap(unique, new):
    """ return the elements which aren't descentants of each other """
    for format,e1 in new:
        #if e1 is an ascendant then replace
        add = True
        for f,e in unique:
            if e1 in [n for n in e.iterancestors()]:
                unique.remove((f,e))
        #if e1 is an descendant don't use it
            if e in [n for n in e1.iterancestors()]:
                add = False
                break
        if add:
            unique.append((format,e1))
    return unique


