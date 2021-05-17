function change_db(name) {
    var change_db_form = document.getElementById('change_db_form');
    var db_input = document.createElement('input');
    db_input.type = "hidden";
    db_input.name = "dbname";
    db_input.value = name;
    change_db_form.append(db_input);
    change_db_form.requestSubmit();
}
