from pathlib import Path
from cofan import Filer, BaseProvider, Server, BaseHandler
from miirad import providers
from miirad.providers import *

working_dir = Path(__file__).parent
miirad_dir = Path(providers.__file__).parent

#after selecting db
db_patterner = PostPatterner()
db_patterner.add('_get_categories$', Categorier)
db_patterner.add('_get_invoices$', InvoiceLister)
db_patterner.add('invoice$', InvoiceViewer)
db_patterner.add('edit_invoice$', InvoiceEditor)
db_patterner.add('delete_invoice$', InvoiceDeleter)
db_patterner.add('edit_categories$', CategoryEditor)
db_patterner.add('$', Indexer)

#after getting session
edit_db = DBEditor(working_dir / 'config')
db_selector = DBSelector(working_dir / 'config', db_patterner)

session_patterner = PostPatterner()
session_patterner.add('edit_db$', edit_db)
session_patterner.add('settings$', SettingsViewer)
session_patterner.add('db_list$', DbLister(working_dir / 'config'))
session_patterner.add('change_db$', DBChanger(working_dir / 'config'))
session_patterner.add('copy_db$', DBCopier(working_dir / 'config'))
session_patterner.add('', db_selector)


#top level
assets = Filer(miirad_dir / 'data/others')
session_provider = Sessioner(session_patterner)

toplevel = PostPatterner()
toplevel.add('__assets__/', assets)
toplevel.add('about$', Filer(miirad_dir / 'data/html/about.html'))
toplevel.add('', session_provider)

templater = Templater(
    miirad_dir / 'data/html/template.html', toplevel)

handler = PostHandler(templater)

srv = Server(('localhost', 8000), handler)

try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass


