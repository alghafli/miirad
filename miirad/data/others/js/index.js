function populate_category_select() {
    var xmlhttp = new XMLHttpRequest();
    var url = "_get_categories";

    xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var myArr = JSON.parse(this.responseText);
            myFunction(myArr);
        }
    };
    xmlhttp.open("GET", url, true);
    xmlhttp.send();

    function myFunction(arr) {
        var out = ['<option value="">اختر تصنيفا</option>'];
        var i;
        for(i = 0; i < arr.length; i++) {
            opt = '<option value="{}">{}</option>'.replace(
                '{}', arr[i]["id"]).replace('{}', arr[i]["name"]);
            out.push(opt);
        }
        document.getElementById("category-input").innerHTML = out.join("\n");
    }
}

function populate_invoice_table() {
    var invoice_table = document.getElementById("invoice-table-body");
    var xmlhttp = new XMLHttpRequest();
    var url = "_get_invoices?{}";
    
    var q = {};
    q['page'] = current_page
    q['q'] = document.getElementById("search-input").value;
    q['category'] = document.getElementById("category-input").value;
    q['year0'] = document.getElementById("year-0-input").value;
    q['month0'] = document.getElementById("month-0-input").value;
    q['day0'] = document.getElementById("day-0-input").value;
    q['year1'] = document.getElementById("year-1-input").value;
    q['month1'] = document.getElementById("month-1-input").value;
    q['day1'] = document.getElementById("day-1-input").value;
    q['value0'] = document.getElementById("value0").value;
    q['value1'] = document.getElementById("value1").value;
    
    var qtext = [];
    
    for (key in q) {
        qtext.push(key + '=' + q[key]);
    }
    qtext = qtext.join('&');
    url = url.replace('{}', qtext)
    
    xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var myArr = JSON.parse(this.responseText);
            myFunction(myArr);
        }
    };
    xmlhttp.open("GET", url, true);
    xmlhttp.send();

    function myFunction(arr) {
        var out = [];
        var i;
        current_page = arr['page'];
        results = arr['results'];
        
        invoice_table.innerHTML = ""
        for(i = 0; i < results.length; i++) {
            results[i][5] = results[i][5].toFixed(2);
            results[i][6] = results[i][6].toFixed(2);
            
            row = invoice_table.insertRow(-1);
            click_link = 'window.location="invoice?id={}";'.replace(
                '{}', results[i][0]);
            row.setAttribute('onclick', click_link);
            for(j = 0; j < results[i].length; j++) {
                row.insertCell(-1).innerHTML = results[i][j];
            }
        }
        page_text = '{} / {}'.replace(
            '{}', current_page + 1).replace('{}', arr['pages'])
        document.getElementById("page_label").innerHTML = page_text
    }
}

function next_page(offset) {
    current_page = current_page + offset;
    populate_invoice_table();
}

function filter_invoices() {
    current_page = 0;
    populate_invoice_table();
}

var current_page = 0
populate_category_select();
populate_invoice_table();
