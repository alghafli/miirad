function on_replace_checkbox_change(checkbox) {
    var name_input = document.getElementById('name-input');
    var name_select = document.getElementById('name-select');
    
    if (checkbox.checked && !name_input.classList.contains('undisplayed')) {
        name_input.classList.add('undisplayed');
    }
    else if (!checkbox.checked && name_input.classList.contains('undisplayed')) {
        name_input.classList.remove('undisplayed');
    }
    
    if (checkbox.checked && name_select.classList.contains('undisplayed')) {
        name_select.classList.remove('undisplayed');
    }
    else if (!checkbox.checked && !name_input.classList.contains('undisplayed')) {
        name_select.classList.add('undisplayed');
    }
}

on_replace_checkbox_change(document.getElementById('replace-checkbox'))
