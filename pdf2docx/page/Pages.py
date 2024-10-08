# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.'''

from collections import Counter
import re
import logging

from .RawPageFactory import RawPageFactory
from ..common.Collection import BaseCollection, Collection
from ..font.Fonts import Fonts


class Pages(BaseCollection):
    '''A collection of ``Page``.'''

    def parse(self, fitz_doc, **settings):
        '''Analyze document structure, e.g. page section, header, footer.

        Args:
            fitz_doc (fitz.Document): ``PyMuPDF`` Document instance.
            settings (dict): Parsing parameters.
        '''
        # ---------------------------------------------
        # 0. extract fonts properties, especially line height ratio
        # ---------------------------------------------
        fonts = Fonts.extract(fitz_doc)

        # ---------------------------------------------
        # 1. extract and then clean up raw page
        # ---------------------------------------------
        pages, raw_pages = [], []
        words_found = False
        for page in self:
            if page.skip_parsing: continue

            # init and extract data from PDF
            raw_page = RawPageFactory.create(page_engine=fitz_doc[page.id], backend='PyMuPDF')
            raw_page.restore(**settings)

            # check if any words are extracted since scanned pdf may be directed
            if not words_found and raw_page.raw_text.strip():
                words_found = True

            # process blocks and shapes based on bbox
            raw_page.clean_up(**settings)

            # process font properties
            raw_page.process_font(fonts)            

            # after this step, we can get some basic properties
            # NOTE: floating images are detected when cleaning up blocks, so collect them here
            page.width = raw_page.width
            page.height = raw_page.height
            page.float_images.reset().extend(raw_page.blocks.floating_image_blocks)

            raw_pages.append(raw_page)
            pages.append(page)

        # show message if no words found
        if not words_found:
            logging.warning('Words count: 0. It might be a scanned pdf, which is not supported yet.')

        
        # ---------------------------------------------
        # 2. parse structure in document/pages level
        # ---------------------------------------------
        # NOTE: blocks structure might be changed in this step, e.g. promote page header/footer,
        # so blocks structure based process, e.g. calculating margin, parse section should be 
        # run after this step.
        Pages._parse_document(raw_pages)


        # ---------------------------------------------
        # 3. parse structure in page level, e.g. page margin, section
        # ---------------------------------------------
        # parse sections
        for page, raw_page in zip(pages, raw_pages):
            # page margin
            margin = raw_page.calculate_margin(**settings)
            raw_page.margin = page.margin = margin

            # page section
            sections = raw_page.parse_section(**settings)
            page.sections.extend(sections)
    

    @staticmethod
    def _parse_document(raw_pages:list):
        '''Parse structure in document/pages level, e.g. header, footer'''
        Pages._parse_header_footer(raw_pages)


    @staticmethod
    def _parse_header_footer(raw_pages:list):
        headers = Counter()
        footers = Counter()
        num_pages = len(raw_pages)
        threshold = int(num_pages * 0.4) if num_pages > 10 else 4
        if 1 < num_pages <= 3:
            threshold = num_pages
        for page in raw_pages:
            elements = Collection()
            elements.extend(page.blocks)
            # elements.extend(page.shapes)
            if not elements: continue
            blocks = page.blocks.sort_in_reading_order()
            for i in range(3):
                if i < len(blocks) and blocks[i].text is not None:
                    block = blocks[i]
                    text = re.sub(r'\d+', '1', block.text.strip())
                    headers[text] += 1
                if i < len(blocks) and blocks[-(i+1)].text is not None:
                    block = blocks[-(i+1)]
                    text = re.sub(r'\d+', '1', block.text.strip())
                    footers[text] += 1

        for page in raw_pages:
            elements = Collection()
            elements.extend(page.blocks)
            # elements.extend(page.shapes)
            if not elements: continue
            blocks = page.blocks.sort_in_reading_order()
            header_blocks = []
            footer_blocks = []
            for i in range(3):
                if i < len(blocks) and blocks[i].text is not None:
                    block = blocks[i]
                    text = re.sub(r'\d+', '1', block.text.strip())
                    if headers[text] > threshold:
                        header_blocks.append(block)
                if i < len(blocks) and blocks[-(i+1)].text is not None:
                    block = blocks[-(i+1)]
                    text = re.sub(r'\d+', '1', block.text.strip())
                    if footers[text] > threshold:
                        footer_blocks.append(block)
            page.header = max([b.bbox[3] for b in header_blocks], default=0)
            page.footer = min([b.bbox[1] for b in footer_blocks], default=page.bbox[3])
