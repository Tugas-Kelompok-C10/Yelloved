"""Definition of the four dashboard tabs, shared by the page and the navbar popover."""

# request = ada yang minta barang. penawaran = ada yang menawarkan barang
TABS = [
    {
        'key': 'incoming', 'label': 'Request Masuk', 'actionable': True,
        'short': 'Orang lain meminta barangmu',
        'description': 'Daftar orang yang meminta barang milikmu. Terima request untuk menandai barang '
                       'tidak tersedia dan membuka kontak peminta, atau tolak jika kurang cocok. '
                       'Saat satu request diterima, request lain untuk barang yang sama otomatis ditolak.',
        'empty': 'Request dari orang lain untuk barangmu akan muncul di sini.',
    },
    {
        'key': 'sent', 'label': 'Request Terkirim', 'actionable': False,
        'short': 'Barang orang lain yang kamu minta',
        'description': 'Barang milik orang lain yang kamu minta. Pantau statusnya di sini, batalkan '
                       'selama masih menunggu, dan lihat kontak pemilik setelah request diterima.',
        'empty': 'Request yang kamu kirim ke pemilik barang akan muncul di sini.',
    },
    {
        'key': 'offers_received', 'label': 'Penawaran Masuk', 'actionable': True,
        'short': 'Barang ditawarkan ke wanted post-mu',
        'description': 'Barang yang ditawarkan orang lain untuk wanted post-mu. Terima penawaran yang '
                       'paling cocok dan wanted post-mu otomatis ditandai terpenuhi, sedangkan '
                       'penawaran lainnya ditolak.',
        'empty': 'Penawaran barang untuk wanted post-mu akan muncul di sini.',
    },
    {
        'key': 'offers_sent', 'label': 'Penawaran Terkirim', 'actionable': False,
        'short': 'Barangmu yang kamu tawarkan',
        'description': 'Barang milikmu yang kamu tawarkan ke wanted post orang lain. Tarik penawaran '
                       'selama masih menunggu, dan lihat kontak pembuat wanted post setelah diterima.',
        'empty': 'Barang yang kamu tawarkan ke wanted post orang lain akan muncul di sini.',
    },
]
TAB_KEYS = tuple(t['key'] for t in TABS)
