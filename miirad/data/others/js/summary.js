function generate_graph(obj_id) {
    var data = [];
    for (i=0;i<12;i++) {
        data.push(Math.round((Math.random()-0.5) * 2000))
    }
    
    var graph_canvas = document.getElementById(obj_id);
    
    ymargin = 20;
    xmargin = 20;
    ylegend_margin = 60;
    xlegend_margin = 20;
    YLEGEND_SEP = 100;
    XLEGEND_SEP = 100;
    
    width = graph_canvas.width
    height = graph_canvas.height
    draw_height = height - 2 * ymargin - xlegend_margin;
    draw_width = width - 2 * xmargin - ylegend_margin;
    xlegends = data.length - 1;
    ylegends = Math.floor(draw_height / YLEGEND_SEP);
    
    ctx = graph_canvas.getContext("2d");
    ctx.font = "20px sans";
    ctx.textBaseline = "middle";
    
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, width, height);
    
    ctx.strokeStyle = "black";
    ctx.beginPath()
    ctx.moveTo(xmargin + ylegend_margin, ymargin)
    ctx.lineTo(xmargin + ylegend_margin, height - ymargin - xlegend_margin)
    ctx.lineTo(width - xmargin, height - ymargin - xlegend_margin)
    ctx.stroke()
    
    var mx = data.length;
    var mn = 1;
    var legend_px_step = draw_width / xlegends;
    
    var px = xmargin + ylegend_margin;
    var pv = mn;
    
    ctx.fillStyle = "black";
    ctx.textAlign = "center";
    while (pv <= mx) {
        var m = ctx.measureText(pv);
        ctx.fillText(pv, px, height - ymargin);
        pv = pv + 1;
        px = px + legend_px_step;
    }
    
    var mx = Math.max.apply(null, data);
    var mn = Math.min.apply(null, data);
    var legend_step = (mx - mn) / ylegends;
    var legend_px_step = draw_height / ylegends;
    
    var py = draw_height + ymargin;
    var pv = mn;
    
    ctx.textAlign = "left";
    while (pv <= mx) {
        var m = ctx.measureText(pv);
        ctx.fillText(pv, xmargin, py);
        pv = pv + legend_step;
        py = py - legend_px_step;
    }
    
    var c = 0;
    var x = draw_width * c / xlegends;
    var y = draw_height * (data[c] - mn) / (mx - mn);
    ctx.beginPath();
    ctx.moveTo(xmargin + ylegend_margin + x, height - ymargin - xlegend_margin - y);
    c++;
    while (c < data.length) {
        var x = draw_width * c / xlegends;
        var y = draw_height * (data[c] - mn) / (mx - mn);
        ctx.lineTo(xmargin + ylegend_margin + x, height - ymargin - xlegend_margin - y);
        c++;
    }
    ctx.stroke();
}

generate_graph('graph_canvas');

