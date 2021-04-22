function show_auto_backups() {
    var auto_backups = document.getElementById('auto-backup-div');
    var named_backups = document.getElementById('named-backup-div');
    if (!named_backups.classList.contains('undisplayed')) {
        named_backups.classList.add('undisplayed');
    }
    if (auto_backups.classList.contains('undisplayed')) {
        auto_backups.classList.remove('undisplayed');
    }
}

function show_named_backups() {
    var auto_backups = document.getElementById('auto-backup-div');
    var named_backups = document.getElementById('named-backup-div');
    if (!auto_backups.classList.contains('undisplayed')) {
        auto_backups.classList.add('undisplayed');
    }
    if (named_backups.classList.contains('undisplayed')) {
        named_backups.classList.remove('undisplayed');
    }
}

