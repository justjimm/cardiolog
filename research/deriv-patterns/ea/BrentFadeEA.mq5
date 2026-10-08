//+------------------------------------------------------------------+
//|                                                  BrentFadeEA.mq5 |
//|  Deriv MT5, UK Brent Oil: early-session fade + weekend gap fade  |
//|                                                                  |
//|  Pattern 1, early-session fade (tested: 171 trades, 56% win,     |
//|    +0.54% net per trade). At FadeDecisionHourGMT (03:00 GMT) the |
//|    move since the 00:00 GMT open is measured. If it exceeds      |
//|    FadeThresholdPct the EA trades AGAINST it at market, with a   |
//|    disaster stop FadeStopPct away, and closes at FadeExitHourGMT.|
//|                                                                  |
//|  Pattern 2, weekend gap fade (tested: 83 trades, 76% win,        |
//|    +0.42% net per trade). On Monday shortly after 00:00 GMT the  |
//|    gap from Friday's last H1 close is measured. If it exceeds    |
//|    WeekendMinGapPct the EA trades AGAINST it with take-profit at |
//|    Friday's close and a time exit before Deriv's 21:00 GMT close.|
//|                                                                  |
//|  All decisions are made in GMT. The EA detects the server's GMT  |
//|  offset automatically (override with GMTOffsetOverrideHours).    |
//|  In the Strategy Tester the server clock is treated as GMT.      |
//+------------------------------------------------------------------+
#property copyright "Deriv pattern study, 2026"
#property version   "1.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

enum ENUM_SIZING_MODE
  {
   SIZE_BY_LEVERAGE = 0,   // Notional = equity x LeverageMultiple
   SIZE_FIXED_LOTS  = 1    // Fixed lots per trade
  };

input group "=== Pattern switches ==="
input bool             EnableEarlyFade        = true;     // Early-session fade (03:00 -> 13:00 GMT)
input bool             EnableWeekendFade      = true;     // Weekend gap fade (Monday)

input group "=== Sizing ==="
input ENUM_SIZING_MODE SizingMode             = SIZE_BY_LEVERAGE;
input double           LeverageMultiple       = 2.0;      // Notional / equity for the early fade
input double           WeekendSizeFactor      = 0.5;      // Weekend trade size as a fraction of early-fade size
input double           FixedLots              = 10.0;     // Used only in SIZE_FIXED_LOTS
input double           MaxLots                = 1000.0;   // Hard cap per trade
input double           MaxDrawdownHaltPct     = 35.0;     // Halt new trades when equity is this % below its peak (0 = off)

input group "=== Early-session fade (GMT) ==="
input double           FadeThresholdPct       = 0.5;      // Min |move| from 00:00 open to decision time, %
input int              FadeDecisionHourGMT    = 3;        // Decision hour (GMT)
input int              FadeDecisionWindowMin  = 10;       // Minutes after the hour during which a decision may be taken
input int              FadeExitHourGMT        = 13;       // Time exit hour (GMT)
input double           FadeStopPct            = 2.0;      // Disaster stop from entry, % (0 = none)

input group "=== Weekend gap fade (GMT) ==="
input double           WeekendMinGapPct       = 0.3;      // Min |gap| from Friday close, %
input int              WeekendEntryDelayMin   = 2;        // Minutes after Monday 00:00 GMT before entering
input int              WeekendEntryWindowMin  = 10;       // Entry allowed until delay + window minutes
input int              WeekendExitHourGMT     = 20;       // Time exit hour (GMT), before Deriv's 21:00 close
input int              WeekendExitMinute      = 50;       // Time exit minute
input double           WeekendStopPct         = 0.0;      // Stop from entry, % (0 = none, as tested)

input group "=== Execution ==="
input int              GMTOffsetOverrideHours = -99;      // Server minus GMT, hours (-99 = detect automatically)
input int              MaxSpreadPoints        = 0;        // Skip entries when spread exceeds this (0 = no filter)
input int              SlippagePoints         = 50;       // Max deviation for market orders
input long             MagicEarly             = 240301;
input long             MagicWeekend           = 240302;
input string           TradeComment           = "BrentFade";

//--- globals
CTrade        trade;
CPositionInfo posinfo;
datetime      g_lastFadeDay     = 0;     // GMT day of the last early-fade decision
datetime      g_lastWeekendDay  = 0;     // GMT day of the last weekend decision
double        g_equityPeak      = 0;
bool          g_halted          = false;
int           g_offsetSeconds   = 0;
datetime      g_offsetUpdated   = 0;
datetime      g_lastProcess     = 0;

//+------------------------------------------------------------------+
string StateKey(const string suffix)
  {
   return "BrentFadeEA_" + _Symbol + "_" + IntegerToString((int)MagicEarly) + "_" + suffix;
  }
//+------------------------------------------------------------------+
void SaveState()
  {
   GlobalVariableSet(StateKey("fadeDay"),    (double)g_lastFadeDay);
   GlobalVariableSet(StateKey("weekendDay"), (double)g_lastWeekendDay);
   GlobalVariableSet(StateKey("peak"),       g_equityPeak);
   GlobalVariableSet(StateKey("halted"),     g_halted ? 1.0 : 0.0);
  }
//+------------------------------------------------------------------+
void LoadState()
  {
   if(GlobalVariableCheck(StateKey("fadeDay")))    g_lastFadeDay    = (datetime)GlobalVariableGet(StateKey("fadeDay"));
   if(GlobalVariableCheck(StateKey("weekendDay"))) g_lastWeekendDay = (datetime)GlobalVariableGet(StateKey("weekendDay"));
   if(GlobalVariableCheck(StateKey("peak")))       g_equityPeak     = GlobalVariableGet(StateKey("peak"));
   if(GlobalVariableCheck(StateKey("halted")))     g_halted         = (GlobalVariableGet(StateKey("halted")) > 0.5);
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetDeviationInPoints(SlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   if(!MQLInfoInteger(MQL_TESTER))
      LoadState();
   if(g_equityPeak <= 0)
      g_equityPeak = AccountInfoDouble(ACCOUNT_EQUITY);
   UpdateOffset(true);
   EventSetTimer(5);
   PrintFormat("BrentFadeEA started on %s. Server-GMT offset %d s. Leverage x%.2f, weekend factor %.2f, halt at %.0f%% drawdown.",
               _Symbol, g_offsetSeconds, LeverageMultiple, WeekendSizeFactor, MaxDrawdownHaltPct);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(!MQLInfoInteger(MQL_TESTER))
      SaveState();
   Comment("");
  }
//+------------------------------------------------------------------+
void OnTick()  { Process(); }
void OnTimer() { Process(); }
//+------------------------------------------------------------------+
//| Server time minus GMT, in seconds                                |
//+------------------------------------------------------------------+
void UpdateOffset(const bool force)
  {
   if(GMTOffsetOverrideHours != -99)
     {
      g_offsetSeconds = GMTOffsetOverrideHours * 3600;
      return;
     }
   if(MQLInfoInteger(MQL_TESTER))
     {
      g_offsetSeconds = 0;        // tester: server clock treated as GMT
      return;
     }
   // TimeCurrent() is the last tick time; only trust it when ticks are fresh
   datetime now = TimeCurrent();
   if(!force && (TimeLocal() - g_offsetUpdated) < 600)
      return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;
   if(TimeGMT() - tick.time > 300 && !force)
      return;                     // stale quote (weekend/holiday): keep the last good offset
   long diff = (long)now - (long)TimeGMT();
   long half = 1800;
   g_offsetSeconds = (int)(MathRound((double)diff / (double)half) * half);
   g_offsetUpdated = TimeLocal();
  }
//+------------------------------------------------------------------+
datetime NowGMT()                   { return (datetime)((long)TimeCurrent() - g_offsetSeconds); }
datetime GmtToServer(datetime gmt)  { return (datetime)((long)gmt + g_offsetSeconds); }
datetime ServerToGmt(datetime srv)  { return (datetime)((long)srv - g_offsetSeconds); }
datetime DayStart(datetime t)       { return (datetime)((long)t - ((long)t % 86400)); }
//+------------------------------------------------------------------+
//| H1 bar whose server time matches a GMT instant                   |
//+------------------------------------------------------------------+
bool H1BarAtGMT(const datetime gmtTime, int &shift)
  {
   datetime st = GmtToServer(gmtTime);
   shift = iBarShift(_Symbol, PERIOD_H1, st, false);
   if(shift < 0)
      return false;
   datetime bt = iTime(_Symbol, PERIOD_H1, shift);
   if(MathAbs((long)bt - (long)st) > 1800)
      return false;               // no bar at that hour (holiday / closed market)
   return true;
  }
//+------------------------------------------------------------------+
int CountPositions(const long magic)
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic)
         n++;
   return n;
  }
//+------------------------------------------------------------------+
void CloseAll(const long magic, const string why)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic)
        {
         if(trade.PositionClose(posinfo.Ticket()))
            PrintFormat("Closed #%I64u (%s): %s", posinfo.Ticket(), posinfo.Comment(), why);
         else
            PrintFormat("Close failed #%I64u: %s (retcode %d)", posinfo.Ticket(), trade.ResultRetcodeDescription(), trade.ResultRetcode());
        }
  }
//+------------------------------------------------------------------+
datetime OldestPositionGmtDay(const long magic)
  {
   datetime oldest = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic)
        {
         datetime t = DayStart(ServerToGmt(posinfo.Time()));
         if(oldest == 0 || t < oldest) oldest = t;
        }
   return oldest;
  }
//+------------------------------------------------------------------+
double CalcLots(const double price, const double factor)
  {
   double lots = 0;
   if(SizingMode == SIZE_FIXED_LOTS)
      lots = FixedLots * factor;
   else
     {
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      double cs     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      if(cs <= 0 || price <= 0 || equity <= 0) return 0;
      lots = equity * LeverageMultiple * factor / (cs * price);
     }
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = vmin > 0 ? vmin : 1.0;
   lots = MathFloor(lots / step) * step;
   lots = MathMin(lots, MathMin(vmax, MaxLots));
   if(lots < vmin)
     {
      PrintFormat("Computed size %.2f lots is below the minimum %.2f; trade skipped. Raise LeverageMultiple or deposit more.", lots, vmin);
      return 0;
     }
   return NormalizeDouble(lots, 8);
  }
//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(MaxSpreadPoints <= 0) return true;
   long sp = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(sp > MaxSpreadPoints)
     {
      PrintFormat("Spread %d points above limit %d; entry skipped.", (int)sp, MaxSpreadPoints);
      return false;
     }
   return true;
  }
//+------------------------------------------------------------------+
bool MarginOk(const ENUM_ORDER_TYPE type, const double lots, const double price)
  {
   double margin = 0;
   if(!OrderCalcMargin(type, _Symbol, lots, price, margin))
      return true;                // cannot compute: let the server decide
   double freem = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(margin > freem * 0.9)
     {
      PrintFormat("Required margin %.2f exceeds 90%% of free margin %.2f; entry skipped.", margin, freem);
      return false;
     }
   return true;
  }
//+------------------------------------------------------------------+
void UpdateEquityPeak()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_equityPeak) g_equityPeak = eq;
   if(MaxDrawdownHaltPct > 0 && g_equityPeak > 0 && !g_halted)
     {
      double dd = 100.0 * (1.0 - eq / g_equityPeak);
      if(dd >= MaxDrawdownHaltPct)
        {
         g_halted = true;
         PrintFormat("HALT: drawdown %.1f%% from peak %.2f. No new trades. Reset by deleting global variable %s or re-attaching with a higher MaxDrawdownHaltPct.",
                     dd, g_equityPeak, StateKey("halted"));
         SaveState();
        }
     }
  }
//+------------------------------------------------------------------+
bool Enter(const long magic, const int dir, const double lots, const double stopPct, const double tpPrice, const string tag)
  {
   trade.SetExpertMagicNumber(magic);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double sl  = 0, tp = tpPrice;
   bool ok;
   if(dir > 0)
     {
      if(stopPct > 0) sl = NormalizeDouble(ask * (1.0 - stopPct / 100.0), dg);
      if(tp > 0 && tp <= ask) tp = 0;           // take-profit must be above the ask for a buy
      if(!MarginOk(ORDER_TYPE_BUY, lots, ask)) return false;
      ok = trade.Buy(lots, _Symbol, 0.0, sl, NormalizeDouble(tp, dg), TradeComment + " " + tag);
     }
   else
     {
      if(stopPct > 0) sl = NormalizeDouble(bid * (1.0 + stopPct / 100.0), dg);
      if(tp > 0 && tp >= bid) tp = 0;           // take-profit must be below the bid for a sell
      if(!MarginOk(ORDER_TYPE_SELL, lots, bid)) return false;
      ok = trade.Sell(lots, _Symbol, 0.0, sl, NormalizeDouble(tp, dg), TradeComment + " " + tag);
     }
   if(ok)
      PrintFormat("%s %s %.2f lots at %.3f, sl %.3f, tp %.3f", tag, dir > 0 ? "BUY" : "SELL", lots, dir > 0 ? ask : bid, sl, tp);
   else
      PrintFormat("%s entry failed: %s (retcode %d)", tag, trade.ResultRetcodeDescription(), trade.ResultRetcode());
   return ok;
  }
//+------------------------------------------------------------------+
//| Main loop, at most once per second                               |
//+------------------------------------------------------------------+
void Process()
  {
   if(TimeLocal() == g_lastProcess) return;   // at most once per second
   g_lastProcess = TimeLocal();
   UpdateOffset(false);
   UpdateEquityPeak();

   datetime gnow = NowGMT();
   MqlDateTime dt;
   TimeToStruct(gnow, dt);
   datetime gday   = DayStart(gnow);
   bool     weekday = (dt.day_of_week >= 1 && dt.day_of_week <= 5);
   double   bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   //--- 1. Exits ------------------------------------------------------
   if(CountPositions(MagicEarly) > 0)
     {
      datetime openedDay = OldestPositionGmtDay(MagicEarly);
      if(dt.hour >= FadeExitHourGMT || openedDay < gday)
         CloseAll(MagicEarly, "early-fade time exit");
     }
   if(CountPositions(MagicWeekend) > 0)
     {
      datetime openedDay = OldestPositionGmtDay(MagicWeekend);
      bool pastExit = (dt.hour > WeekendExitHourGMT) || (dt.hour == WeekendExitHourGMT && dt.min >= WeekendExitMinute);
      if(pastExit || openedDay < gday || dt.day_of_week != 1)
         CloseAll(MagicWeekend, "weekend-fade time exit");
     }

   //--- 2. Early-session fade entry -----------------------------------
   if(EnableEarlyFade && weekday && !g_halted
      && dt.hour == FadeDecisionHourGMT && dt.min < FadeDecisionWindowMin
      && g_lastFadeDay != gday && CountPositions(MagicEarly) == 0)
     {
      int sh;
      if(!H1BarAtGMT(gday, sh))
        {
         PrintFormat("No 00:00 GMT bar found for %s; early fade skipped today.", TimeToString(gday, TIME_DATE));
         g_lastFadeDay = gday; SaveState();
        }
      else
        {
         double open0 = iOpen(_Symbol, PERIOD_H1, sh);
         double move  = 100.0 * (bid / open0 - 1.0);
         g_lastFadeDay = gday; SaveState();           // one decision per day, trade or not
         PrintFormat("Early fade check %s: 00:00 open %.3f, now %.3f, move %+.2f%% (threshold %.2f%%)",
                     TimeToString(gnow, TIME_DATE | TIME_MINUTES), open0, bid, move, FadeThresholdPct);
         if(MathAbs(move) > FadeThresholdPct && SpreadOk())
           {
            int dir = (move > 0) ? -1 : +1;          // fade: sell after a rise, buy after a drop
            double lots = CalcLots(bid, 1.0);
            if(lots > 0) Enter(MagicEarly, dir, lots, FadeStopPct, 0.0, "EarlyFade");
           }
        }
     }

   //--- 3. Weekend gap fade entry -------------------------------------
   if(EnableWeekendFade && dt.day_of_week == 1 && !g_halted
      && dt.hour == 0 && dt.min >= WeekendEntryDelayMin && dt.min < WeekendEntryDelayMin + WeekendEntryWindowMin
      && g_lastWeekendDay != gday && CountPositions(MagicWeekend) == 0)
     {
      int sh;
      if(!H1BarAtGMT(gday, sh))
        {
         PrintFormat("No Monday 00:00 GMT bar yet for %s; waiting.", TimeToString(gday, TIME_DATE));
        }
      else
        {
         datetime prevBarTime = iTime(_Symbol, PERIOD_H1, sh + 1);
         double   fridayClose = iClose(_Symbol, PERIOD_H1, sh + 1);
         g_lastWeekendDay = gday; SaveState();
         if(ServerToGmt(prevBarTime) > gday - 36 * 3600)
            PrintFormat("Previous H1 bar is %s, not a Friday bar; weekend fade skipped.", TimeToString(prevBarTime));
         else
           {
            double gap = 100.0 * (bid / fridayClose - 1.0);
            PrintFormat("Weekend gap check: Friday close %.3f, now %.3f, gap %+.2f%% (min %.2f%%)", fridayClose, bid, gap, WeekendMinGapPct);
            if(MathAbs(gap) >= WeekendMinGapPct && SpreadOk())
              {
               int dir = (gap > 0) ? -1 : +1;
               double lots = CalcLots(bid, WeekendSizeFactor);
               if(lots > 0) Enter(MagicWeekend, dir, lots, WeekendStopPct, fridayClose, "WeekendFade");
              }
           }
        }
     }

   //--- 4. Chart status -----------------------------------------------
   Comment(StringFormat("BrentFadeEA  GMT %s  |  server-GMT offset %+d h  |  equity %.2f  peak %.2f  %s\nEarly fade: %s, last decision %s, open %d  |  Weekend fade: %s, last decision %s, open %d",
                        TimeToString(gnow, TIME_DATE | TIME_MINUTES), g_offsetSeconds / 3600,
                        AccountInfoDouble(ACCOUNT_EQUITY), g_equityPeak, g_halted ? "HALTED" : "",
                        EnableEarlyFade ? "on" : "off", TimeToString(g_lastFadeDay, TIME_DATE), CountPositions(MagicEarly),
                        EnableWeekendFade ? "on" : "off", TimeToString(g_lastWeekendDay, TIME_DATE), CountPositions(MagicWeekend)));
  }
//+------------------------------------------------------------------+
