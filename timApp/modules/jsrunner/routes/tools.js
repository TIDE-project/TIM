class Tools {

    constructor(data) {
        this.data = data;
        this.final_result = {};
    }

    getDouble(fieldName, def=0) {
        //console.log(fieldName);
        var fn = '71.'+fieldName;
        var s = this.data.fields[fn];
        //console.log(fn + " => " +s);
        let r = parseFloat(s);
        if (r === NaN) r = def;
        return r;
    }

    getSum(a, b) {
        return a + b;
    }

    setString(fieldName, content) {
        var tidFN = '71.'+fieldName;
        console.log(tidFN);
        this.final_result[tidFN] = content;
    }

    setDouble(fieldName, content) {
        var tidFN = '71.'+fieldName;
        this.final_result[tidFN] = content;
    }

    getResult() {
        return {'user': this.data.user.id, 'fields':  this.final_result};
    }
}

module.exports = Tools;
