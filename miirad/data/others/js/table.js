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

