// Google Cloud Storage Text to BigQuery classic batch template UDF.
// Synthetic fixture has no quoted commas or header row.
function transform(line) {
  var columns = line.split(",");
  return JSON.stringify({
    id: parseInt(columns[0], 10),
    topic: columns[1],
    minutes: parseInt(columns[2], 10),
  });
}
