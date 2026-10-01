window.NIGHTAZIMUTH_CONFIG = {
  // Public API origin for the hosted site. This file is public: never add secrets.
  apiBaseUrl: "https://api.nightazimuth.co.uk"
};

// Load the observability latency interceptor synchronously here so it is installed
// before observability.js and the application begin issuing API requests. The
// script is same-origin and contains no configuration or secrets.
document.write('<script src="./observability-latency.js?v=22.1.0"><\/script>');
