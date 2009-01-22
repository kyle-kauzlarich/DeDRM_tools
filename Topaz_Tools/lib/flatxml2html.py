#! /usr/bin/python
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab

from __future__ import with_statement
import csv
import sys
import os
import getopt
from struct import pack
from struct import unpack


class DocParser(object):
    def __init__(self, flatxml, classlst, fileid):
        self.id = os.path.basename(fileid).replace('.dat','')
        self.docList = flatxml.split('\n')
        self.docSize = len(self.docList)
        self.classList = {}
        tmpList = classlst.split('\n')
        for pclass in tmpList:
            if pclass != '':
                # remove the leading period from the css name
                cname = pclass[1:]
            self.classList[cname] = True
        self.ocrtext = []
        self.link_id = []
        self.link_title = []
        self.link_page = []
        self.dehyphen_rootid = []
        self.paracont_stemid = []
        self.parastems_stemid = []

    # return tag at line pos in document
    def lineinDoc(self, pos) :
        if (pos >= 0) and (pos < self.docSize) :
            item = self.docList[pos]
            if item.find('=') >= 0:
                (name, argres) = item.split('=',1)
            else : 
                name = item
                argres = ''
        return name, argres

        
    # find tag in doc if within pos to end inclusive
    def findinDoc(self, tagpath, pos, end) :
        result = None
        if end == -1 :
            end = self.docSize
        else:
            end = min(self.docSize, end)
        foundat = -1
        for j in xrange(pos, end):
            item = self.docList[j]
            if item.find('=') >= 0:
                (name, argres) = item.split('=',1)
            else : 
                name = item
                argres = ''
            if name.endswith(tagpath) : 
                result = argres
                foundat = j
                break
        return foundat, result


    # return list of start positions for the tagpath
    def posinDoc(self, tagpath):
        startpos = []
        pos = 0
        res = ""
        while res != None :
            (foundpos, res) = self.findinDoc(tagpath, pos, -1)
            if res != None :
                startpos.append(foundpos)
            pos = foundpos + 1
        return startpos


    # build a description of the paragraph
    def getParaDescription(self, start, end):

        result = []

        # paragraph
        (pos, pclass) = self.findinDoc('paragraph.class',start,end) 

        # class names are an issue given topaz may start them with numerals (not allowed),
        # use a mix of cases (which cause some browsers problems), and actually
        # attach numbers after "_reclustered*" to the end to deal classeses that inherit
        # from a base class (but then not actually provide all of these _reclustereed 
        # classes in the stylesheet!

        # so we clean this up by lowercasing, prepend 'cl-', and getting any baseclass
        # that exists in the stylesheet first, and then adding this specific class
        # after
        if pclass != None :
            classres = ''
            pclass = pclass.lower()
            pclass = 'cl-' + pclass
            p = pclass.find('_')
            if p > 0 :
                baseclass = pclass[0:p]
                if baseclass in self.classList:
                    classres += baseclass + ' '
            classres += pclass
            pclass = classres

        # build up a description of the paragraph in result and return it
        # first check for the  basic - all words paragraph
        (pos, sfirst) = self.findinDoc('paragraph.firstWord',start,end)
        (pos, slast) = self.findinDoc('paragraph.lastWord',start,end)
        if (sfirst != None) and (slast != None) :
            first = int(sfirst)
            last = int(slast)
            for wordnum in xrange(first, last):
                result.append(('ocr', wordnum))
            return pclass, result

        # this type of paragrph may be made up of multiple _spans, inline 
        # word monograms (images) and words with semantic meaning
        # and now a new type "span" versus the old "_span"
        
        # need to parse this type line by line
        line = start + 1
        word_class = ''

        # if end is -1 then we must search to end of document
        if end == -1 :
            end = self.docSize

        while (line < end) :

            (name, argres) = self.lineinDoc(line)

            if name.endswith('span.firstWord') :
                first = int(argres)
                (name, argres) = self.lineinDoc(line+1)
                if not name.endswith('span.lastWord'):
                    print 'Error: - incorrect _span ordering inside paragraph'
                last = int(argres)
                for wordnum in xrange(first, last):
                    result.append(('ocr', wordnum))
                line += 1

            elif name.endswith('word.class'):
               (cname, space) = argres.split('-',1)
               if space == '' : space = '0'
               if (cname == 'spaceafter') and (int(space) > 0) :
                   word_class = 'sa'

            elif name.endswith('word.img.src'):
                result.append(('img' + word_class, int(argres)))
                word_class = ''

            elif name.endswith('word_semantic.firstWord'):
                first = int(argres)
                (name, argres) = self.lineinDoc(line+1)
                if not name.endswith('word_semantic.lastWord'):
                    print 'Error: - incorrect word_semantic ordering inside paragraph'
                last = int(argres)
                for wordnum in xrange(first, last):
                    result.append(('ocr', wordnum))
                line += 1
                              
            line += 1

        return pclass, result
                            

    def buildParagraph(self, pclass, pdesc, type, regtype) :
        parares = ''
        sep =''

        classres = ''
        if pclass :
            classres = ' class="' + pclass + '"'

        br_lb = (regtype == 'fixed') or (regtype == 'chapterheading') or (regtype == 'vertical')

        handle_links = len(self.link_id) > 0
        
        if (type == 'full') or (type == 'begin') :
            parares += '<p' + classres + '>'

        if (type == 'end'):
            parares += ' '

        cnt = len(pdesc)

        for j in xrange( 0, cnt) :

            (wtype, num) = pdesc[j]

            if wtype == 'ocr' :
                word = self.ocrtext[num]
                sep = ' '

                if handle_links:
                    link = self.link_id[num]
                    if (link > 0): 
                        title = self.link_title[link-1]
                        if (title == "") or (parares.rfind(title) < 0): 
                            title='_link_'
                        ptarget = self.link_page[link-1] - 1
                        linkhtml = '<a href="#page%04d">' % ptarget
                        linkhtml += title + '</a>'
                        pos = parares.rfind(title)
                        if pos >= 0:
                            parares = parares[0:pos] + linkhtml + parares[pos+len(title):]
                        else :
                            parares += linkhtml
                        if word == '_link_' : word = ''
                    elif (link < 0) :
                        if word == '_link_' : word = ''

                if word == '_lb_':
                    if ((num-1) in self.dehyphen_rootid ) or handle_links:
                        word = ''
                        sep = ''
                    elif br_lb :
                        word = '<br />\n'
                        sep = ''
                    else :
                        word = '\n'
                        sep = ''

                if num in self.dehyphen_rootid :
                    word = word[0:-1]
                    sep = ''

                parares += word + sep

            elif wtype == 'img' :
                sep = ''
                parares += '<img src="img/img%04d.jpg" alt="" />' % num
                parares += sep

            elif wtype == 'imgsa' :
                sep = ' '
                parares += '<img src="img/img%04d.jpg" alt="" />' % num
                parares += sep

        if len(sep) > 0 : parares = parares[0:-1]
        if (type == 'full') or (type == 'end') :
            parares += '</p>'
        return parares


    
    # walk the document tree collecting the information needed
    # to build an html page using the ocrText

    def process(self):

        htmlpage = ''

        # get the ocr text
        (pos, argres) = self.findinDoc('info.word.ocrText',0,-1)
        if argres :  self.ocrtext = argres.split('|')

        # get information to dehyphenate the text
        (pos, argres) = self.findinDoc('info.dehyphen.rootID',0,-1)
        if argres: 
            argList = argres.split('|')
            self.dehyphen_rootid = [ int(strval) for strval in argList]

        # determine if first paragraph is continued from previous page
        (pos, self.parastems_stemid) = self.findinDoc('info.paraStems.stemID',0,-1)
        first_para_continued = (self.parastems_stemid  != None) 
        
        # determine if last paragraph is continued onto the next page
        (pos, self.paracont_stemid) = self.findinDoc('info.paraCont.stemID',0,-1)
        last_para_continued = (self.paracont_stemid != None)

        # collect link ids
        (pos, argres) = self.findinDoc('info.word.link_id',0,-1)
        if argres:
            argList = argres.split('|')
            self.link_id = [ int(strval) for strval in argList]

        # collect link destination page numbers
        (pos, argres) = self.findinDoc('info.links.page',0,-1)
        if argres :
            argList = argres.split('|')
            self.link_page = [ int(strval) for strval in argList]

        # collect link titles
        (pos, argres) = self.findinDoc('info.links.title',0,-1)
        if argres :
            self.link_title = argres.split('|')
        else:
            self.link_title.append('')


        # get page type
        (pos, pagetype) = self.findinDoc('page.type',0,-1)


        # generate a list of each region starting point
        # each region has one paragraph,, or one image, or one chapterheading

        regionList= self.posinDoc('region')
        regcnt = len(regionList)
        regionList.append(-1)

        anchorSet = False
        breakSet = False

        # process each region tag and convert what you can to html

        for j in xrange(regcnt):

            start = regionList[j]
            end = regionList[j+1]

            (pos, regtype) = self.findinDoc('region.type',start,end)

            # set anchor for link target on this page
            if not anchorSet and not first_para_continued:
                htmlpage += '<div style="visibility: hidden; height: 0; width: 0;" id="' + self.id + '" title="pagetype_' + pagetype + '"></div>\n'
                anchorSet = True

            if regtype == 'graphic' :
                (pos, simgsrc) = self.findinDoc('img.src',start,end)
                if simgsrc:
                    htmlpage += '<div class="graphic"><img src="img/img%04d.jpg" alt="" /></div>' % int(simgsrc)

            
            elif regtype == 'chapterheading' :
                (pclass, pdesc) = self.getParaDescription(start,end)
                if not breakSet:
                    htmlpage += '<div style="page-break-after: always;">&nbsp;</div>\n'
                    breakSet = True
                tag = 'h1'
                if pclass and (len(pclass) >= 7):
                    if pclass[3:7] == 'ch1-' : tag = 'h1'
                    if pclass[3:7] == 'ch2-' : tag = 'h2'
                    if pclass[3:7] == 'ch3-' : tag = 'h3'
                    htmlpage += '<' + tag + ' class="' + pclass + '">'
                else:
                    htmlpage += '<' + tag + '>'
                htmlpage += self.buildParagraph(pclass, pdesc, 'middle', regtype)
                htmlpage += '</' + tag + '>'


            elif (regtype == 'text') or (regtype == 'fixed') or (regtype == 'insert') or (regtype == 'listitem'):
                ptype = 'full'
                # check to see if this is a continution from the previous page
                if first_para_continued :
                    ptype = 'end'
                    first_para_continued = False
                (pclass, pdesc) = self.getParaDescription(start,end)
                if pclass and (len(pclass) >= 6) and (ptype == 'full'):
                    tag = 'p'
                    if pclass[3:6] == 'h1-' : tag = 'h4'
                    if pclass[3:6] == 'h2-' : tag = 'h5'
                    if pclass[3:6] == 'h3-' : tag = 'h6'
                    htmlpage += '<' + tag + ' class="' + pclass + '">'
                    htmlpage += self.buildParagraph(pclass, pdesc, 'middle', regtype)
                    htmlpage += '</' + tag + '>'
                else :
                    htmlpage += self.buildParagraph(pclass, pdesc, ptype, regtype)


            elif (regtype == 'tocentry') :
                ptype = 'full'
                if first_para_continued :
                    ptype = 'end'
                    first_para_continued = False
                (pclass, pdesc) = self.getParaDescription(start,end)
                htmlpage += self.buildParagraph(pclass, pdesc, ptype, regtype)


            elif (regtype == 'vertical') :
                ptype = 'full'
                if first_para_continued :
                    ptype = 'end'
                    first_para_continued = False
                (pclass, pdesc) = self.getParaDescription(start,end)
                htmlpage += self.buildParagraph(pclass, pdesc, ptype, regtype)


            elif (regtype == 'table') :
                ptype = 'full'
                if first_para_continued :
                    ptype = 'end'
                    first_para_continued = False
                (pclass, pdesc) = self.getParaDescription(start,end)
                htmlpage += self.buildParagraph(pclass, pdesc, ptype, regtype)
                print "Warnings - Table Conversions are notoriously poor"
                print "Strongly recommend taking a screen capture image of the "
                print "table in %s.svg and using it to replace this attempt at a table" % self.id


            elif (regtype == 'synth_fcvr.center') or (regtype == 'synth_text.center'):
                (pos, simgsrc) = self.findinDoc('img.src',start,end)
                if simgsrc:
                    htmlpage += '<div class="graphic"><img src="img/img%04d.jpg" alt="" /></div>' % int(simgsrc)


            else :
                print 'Warning: region type', regtype
                (pos, temp) = self.findinDoc('paragraph',start,end)
                if pos != -1:
                    print '   is a "text" region'
                    regtype = 'fixed'
                    ptype = 'full'
                    # check to see if this is a continution from the previous page
                    if first_para_continued :
                        ptype = 'end'
                        first_para_continued = False
                    (pclass, pdesc) = self.getParaDescription(start,end)
                    if pclass and (ptype == 'full') and (len(pclass) >= 6):
                        tag = 'p'
                        if pclass[3:6] == 'h1-' : tag = 'h4'
                        if pclass[3:6] == 'h2-' : tag = 'h5'
                        if pclass[3:6] == 'h3-' : tag = 'h6'
                        htmlpage += '<' + tag + ' class="' + pclass + '">'
                        htmlpage += self.buildParagraph(pclass, pdesc, 'middle', regtype)
                        htmlpage += '</' + tag + '>'
                    else :
                        htmlpage += self.buildParagraph(pclass, pdesc, ptype, regtype)
                else :
                    print '    is a "graphic" region'
                    (pos, simgsrc) = self.findinDoc('img.src',start,end)
                    if simgsrc:
                        htmlpage += '<div class="graphic"><img src="img/img%04d.jpg" alt="" /></div>' % int(simgsrc)


        if last_para_continued :
            if htmlpage[-4:] == '</p>':
                htmlpage = htmlpage[0:-4]
            last_para_continued = False

        return htmlpage



def convert2HTML(flatxml, classlst, fileid):

    # create a document parser
    dp = DocParser(flatxml, classlst, fileid)

    htmlpage = dp.process()

    return htmlpage
