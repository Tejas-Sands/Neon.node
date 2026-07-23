export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      
      let targetDomain = "graph.facebook.com"; // Default for backward compatibility
      
      // If the client sends a custom header, route to that domain instead
      const customDomain = request.headers.get("x-target-domain");
      if (customDomain) {
          targetDomain = customDomain;
      }
      
      const targetUrl = "https://" + targetDomain + url.pathname + url.search;

      const requestOptions = {
        method: request.method,
        headers: new Headers(request.headers),
      };
      
      // Remove the custom header before forwarding
      requestOptions.headers.delete("x-target-domain");

      // Pass the body along for POST/PUT requests
      if (request.method !== "GET" && request.method !== "HEAD") {
        requestOptions.body = request.body;
      }

      // Crucial: Override the Host header to match the target domain
      requestOptions.headers.set("Host", targetDomain);

      const response = await fetch(targetUrl, requestOptions);
      
      // Return response with CORS headers
      const newResponse = new Response(response.body, response);
      newResponse.headers.set("Access-Control-Allow-Origin", "*");
      return newResponse;
      
    } catch (err) {
      return new Response(JSON.stringify({
        error: "Proxy Worker Error",
        message: err.message,
        stack: err.stack
      }), {
        status: 500,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
  }
};
