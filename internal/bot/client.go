package bot

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

const ExchangeURL = "https://api.poloniex.com"

type Client struct {
	BaseURL, Key, Secret string
	HTTP                 *http.Client
	mu                   sync.Mutex
	next                 time.Time
}

func NewClient(key, secret string) *Client {
	return &Client{BaseURL: ExchangeURL, Key: key, Secret: secret, HTTP: &http.Client{Timeout: 15 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect refused") }}}
}
func canonical(method, path string, q url.Values, body []byte, stamp string) string {
	v := url.Values{}
	for k, values := range q {
		v[k] = append([]string(nil), values...)
	}
	v.Set("signTimestamp", stamp)
	if len(body) > 0 {
		// Poloniex signs write bodies as the raw JSON string, never URL-encoded
		// (official SDK: requestBody={body}&signTimestamp={ts}).
		return method + "\n" + path + "\nrequestBody=" + string(body) + "&signTimestamp=" + stamp
	}
	return method + "\n" + path + "\n" + strings.ReplaceAll(v.Encode(), "+", "%20")
}

// HTTPError reports a non-2xx exchange response so callers can distinguish a
// definite "unknown order" (404) from transport ambiguity.
type HTTPError struct {
	Method, Path string
	Status       int
}

func (e *HTTPError) Error() string { return fmt.Sprintf("%s %s HTTP %d", e.Method, e.Path, e.Status) }
func signature(secret, message string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(message))
	return base64.StdEncoding.EncodeToString(m.Sum(nil))
}

// Requests are paced. Writes are never retried: any ambiguous result must be reconciled.
func (c *Client) request(ctx context.Context, method, path string, q url.Values, body any, private bool, out any) error {
	if !strings.HasPrefix(path, "/") || strings.ContainsAny(path, "?#") {
		return errors.New("invalid API path")
	}
	if private && (c.Key == "" || c.Secret == "") {
		return errors.New("poloniex credentials missing")
	}
	c.mu.Lock()
	delay := time.Until(c.next)
	if delay < 0 {
		delay = 0
	}
	c.next = time.Now().Add(delay + 150*time.Millisecond)
	c.mu.Unlock()
	if delay > 0 {
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	} else if err := ctx.Err(); err != nil {
		return err
	}
	var raw []byte
	var err error
	if body != nil {
		raw, err = json.Marshal(body)
		if err != nil {
			return err
		}
	}
	target := c.BaseURL + path
	if len(q) > 0 {
		target += "?" + q.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, method, target, bytes.NewReader(raw))
	if err != nil {
		return errors.New("invalid request")
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if private {
		stamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
		req.Header.Set("key", c.Key)
		req.Header.Set("signTimestamp", stamp)
		req.Header.Set("signatureMethod", "HmacSHA256")
		req.Header.Set("signatureVersion", "2")
		req.Header.Set("recvWindow", "10000")
		req.Header.Set("signature", signature(c.Secret, canonical(method, path, q, raw, stamp)))
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("%s %s transport failed", method, path)
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20+1))
	if err != nil {
		return errors.New("response read failed")
	}
	if len(b) > 8<<20 {
		return errors.New("response too large")
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return &HTTPError{Method: method, Path: path, Status: resp.StatusCode}
	}
	var apiErr struct {
		Code json.RawMessage `json:"code"`
	}
	if json.Unmarshal(b, &apiErr) == nil && len(apiErr.Code) > 0 && string(apiErr.Code) != "0" && string(apiErr.Code) != "200" {
		return fmt.Errorf("%s %s exchange error code %s", method, path, apiErr.Code)
	}
	if err = json.Unmarshal(b, out); err != nil {
		return fmt.Errorf("%s %s invalid response", method, path)
	}
	return nil
}

type Balance struct {
	Currency  string `json:"currency"`
	Available string `json:"available"`
	Hold      string `json:"hold"`
}
type Account struct {
	Type     string    `json:"accountType"`
	Balances []Balance `json:"balances"`
}

func (c *Client) Balances(ctx context.Context) ([]Account, error) {
	var a []Account
	e := c.request(ctx, "GET", "/accounts/balances", nil, nil, true, &a)
	return a, e
}

type Margin struct {
	Used        string `json:"usedMargin"`
	Maintenance string `json:"maintenanceMargin"`
	Free        string `json:"freeMargin"`
	Value       string `json:"totalAccountValue"`
}

func (c *Client) Margin(ctx context.Context) (Margin, error) {
	var m Margin
	e := c.request(ctx, "GET", "/margin/accountMargin", url.Values{"accountType": {"SPOT"}}, nil, true, &m)
	return m, e
}

type Borrow struct {
	Currency string `json:"currency"`
	Borrowed string `json:"borrowed"`
}

func (c *Client) Borrowing(ctx context.Context) ([]Borrow, error) {
	var b []Borrow
	e := c.request(ctx, "GET", "/margin/borrowStatus", nil, nil, true, &b)
	return b, e
}

type Order struct {
	Symbol      string `json:"symbol"`
	Side        string `json:"side"`
	Type        string `json:"type"`
	TimeInForce string `json:"timeInForce"`
	AccountType string `json:"accountType"`
	Price       string `json:"price"`
	Quantity    string `json:"quantity"`
	ClientID    string `json:"clientOrderId"`
	AllowBorrow bool   `json:"allowBorrow"`
}
type OrderResult struct {
	ID             string `json:"id"`
	ClientID       string `json:"clientOrderId"`
	Symbol         string `json:"symbol"`
	Side           string `json:"side"`
	State          string `json:"state"`
	FilledQuantity string `json:"filledQuantity"`
	FilledAmount   string `json:"filledAmount"`
}

func (c *Client) OpenOrders(ctx context.Context) ([]OrderResult, error) {
	var r []OrderResult
	e := c.request(ctx, "GET", "/orders", url.Values{"limit": {"2000"}}, nil, true, &r)
	return r, e
}
func (c *Client) Place(ctx context.Context, o Order) (OrderResult, error) {
	var r OrderResult
	if o.AllowBorrow || o.Type != "LIMIT" || o.TimeInForce != "IOC" || o.AccountType != "SPOT" || o.ClientID == "" || (o.Side != "BUY" && o.Side != "SELL") {
		return r, errors.New("unsafe order")
	}
	e := c.request(ctx, "POST", "/orders", nil, o, true, &r)
	return r, e
}
func (c *Client) Lookup(ctx context.Context, id string) (OrderResult, error) {
	var r OrderResult
	e := c.request(ctx, "GET", "/orders/cid:"+url.PathEscape(id), nil, nil, true, &r)
	return r, e
}

type Trade struct {
	ID          string `json:"id"`
	OrderID     string `json:"orderId"`
	Symbol      string `json:"symbol"`
	Side        string `json:"side"`
	Quantity    string `json:"quantity"`
	Amount      string `json:"amount"`
	FeeCurrency string `json:"feeCurrency"`
	FeeAmount   string `json:"feeAmount"`
}

func (c *Client) Trades(ctx context.Context, id string) ([]Trade, error) {
	var t []Trade
	e := c.request(ctx, "GET", "/orders/"+url.PathEscape(id)+"/trades", nil, nil, true, &t)
	return t, e
}
