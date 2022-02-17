new_item_count = 0

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

function add_invoice_item(button) {
    tbody = button.parentElement.parentElement.parentElement;
    value_type = tbody.parentElement.id.split("-")[0];
    
    var row = tbody.insertRow(tbody.rows.length-1);
    
    var cell = row.insertCell(-1);
    cell.innerHTML = '<button class="button large-text" onclick="remove_row(this);">حذف</button>';
    
    var cell = row.insertCell(-1);
    cell.innerHTML = '<input name="{}-{}-name" form="invoice_form" placeholder="اسم البند" class="default-input" required>'.replace('{}', value_type).replace('{}', new_item_count);
    
    var cell = row.insertCell(-1);
    cell.innerHTML = '<input name="{}-{}-{}" form="invoice_form" type="number" min="0" step="0.01" placeholder="القيمة" class="default-input" required>'.replace('{}', value_type).replace('{}', new_item_count).replace('{}', value_type);
    
    var cell = row.insertCell(-1);
    cell.innerHTML = '<input name="{}-{}-remark" form="invoice_form" placeholder="ملاحظات" class="default-input">'.replace('{}', value_type).replace('{}', new_item_count);
    new_item_count = new_item_count + 1;
}

function show_incomes() {
    var incomes = document.getElementById('income-div');
    var expenses = document.getElementById('expense-div');
    if (!expenses.classList.contains('undisplayed')) {
        expenses.classList.add('undisplayed');
    }
    if (incomes.classList.contains('undisplayed')) {
        incomes.classList.remove('undisplayed');
    }
    
    var income_button = document.querySelector('.income-button');
    var expense_button = document.querySelector('.expense-button');
    if (!expense_button.classList.contains('unselected')) {
        expense_button.classList.add('unselected');
    }
    if (income_button.classList.contains('unselected')) {
        income_button.classList.remove('unselected');
    }
}

function show_expenses() {
    var incomes = document.getElementById('income-div');
    var expenses = document.getElementById('expense-div');
    if (!incomes.classList.contains('undisplayed')) {
        incomes.classList.add('undisplayed');
    }
    if (expenses.classList.contains('undisplayed')) {
        expenses.classList.remove('undisplayed');
    }
    
    var income_button = document.querySelector('.income-button');
    var expense_button = document.querySelector('.expense-button');
    if (!income_button.classList.contains('unselected')) {
        income_button.classList.add('unselected');
    }
    if (expense_button.classList.contains('unselected')) {
        expense_button.classList.remove('unselected');
    }
}

var template = document.querySelector('.save_button');
var nav_bar = document.querySelector('.nav ul.main');

save_button = template.content.cloneNode(true);
nav_bar.appendChild(save_button);
