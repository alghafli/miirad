new_cat_count = 0

function remove_row(button) {
    var row = button
    var count = 0;
    while (count < 4) {
        count ++;
        var row = row.parentElement;
        if (row.tagName == "TR") {
            row.remove()
            break
        }
    }
}

function add_category(button) {
    tbody = button.parentElement.parentElement.parentElement
    var row = tbody.insertRow(tbody.rows.length-2)
    
    var cell = row.insertCell(-1);
    cell.innerHTML = '<input form="save_form" placeholder="اسم التصنيف" name="new_{}" class="default-input"/>'.replace('{}', new_cat_count);
    var cell = row.insertCell(-1);
    cell.innerHTML = '<button class="button" onclick="remove_row(this)">حذف</button>';
    new_cat_count = new_cat_count + 1
}

