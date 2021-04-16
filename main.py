from pathlib import Path
from cofan import Filer, BaseProvider, Server, BaseHandler
from miirad import providers, utils
from miirad.providers import *
import time
import argparse

parser = argparse.ArgumentParser(
    description='Miirad server. Track your incomes and expenses')
parser.add_argument(
    '-a', '--addr', type=str, action='store', default='localhost:8000',
    help='server address in the form <ip> or <ip>:<port>'
)
parser.add_argument(
    '-c', '--config', type=str, action='store',
    default=str(Path(__file__).parent / 'config'),
    help='configuration directory'
)

args = parser.parse_args()

addr = args.addr.split(':')
if len(addr) > 1:
    addr, port = addr
    port = int(port)
else:
    addr = addr[0]
    port = 8000

config_dir = Path(args.config)
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
edit_db = DBEditor(config_dir)
db_selector = DBSelector(config_dir, db_patterner)

session_patterner = PostPatterner()
session_patterner.add('edit_db$', edit_db)
session_patterner.add('settings$', SettingsViewer)
session_patterner.add('db_list$', DbLister(config_dir))
session_patterner.add('change_db$', DBChanger(config_dir))
session_patterner.add('copy_db$', DBCopier(config_dir))
session_patterner.add('', db_selector)


#top level
assets = Filer(miirad_dir / 'data/others')
session_provider = Sessioner(session_patterner)

toplevel = PostPatterner()
toplevel.add('__assets__/', assets)
toplevel.add('about$', Texter(miirad_dir / 'data/html/about.html'))
toplevel.add('', session_provider)

templater = Templater(
    miirad_dir / 'data/html/template.html', toplevel)

handler = PostHandler(templater)

srv = Server((addr, port), handler)

try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass


dbp = config_dir / 'db'
bup = config_dir / 'backup'
bup.mkdir(parents=True, exist_ok=True)
t = int(time.time())
for f in dbp.iterdir():
    name = f.name
    tmp_f = bup / 'temp_{}'.format(f.name)
    bu_f = bup / '{}_{}.sqlite3'.format(f.stem, t)
    print('creating {} backup'.format(f.stem))
    try:
        utils.backup(f, tmp_f)
        tmp_f.rename(bu_f)
    except:
        print('failed to backup {}'.format(f.name))
        tmp_f.unlink(missing_ok=True)
    
    c = sorted(bup.glob('{}_*'.format(f.stem)),
        key=lambda f: f.stem.split('_', 1)[1], reverse=True)
    while len(c) > 10:
        c.pop().unlink(missing_ok=True)

