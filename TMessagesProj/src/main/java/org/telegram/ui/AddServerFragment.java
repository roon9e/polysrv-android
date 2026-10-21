package org.telegram.ui;

import static org.telegram.messenger.AndroidUtilities.dp;

import android.content.Context;
import android.graphics.Color;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.R;
import org.telegram.polysrv.PolySrvServer;
import org.telegram.polysrv.PolySrvServers;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.Components.EditTextBoldCursor;
import org.telegram.ui.Components.LayoutHelper;

public class AddServerFragment extends BaseFragment {

    public interface OnSavedListener {
        void onSaved(PolySrvServer server);
    }

    private final PolySrvServer editingServer;
    private final OnSavedListener onSavedListener;

    private EditTextBoldCursor nameField;
    private EditTextBoldCursor hostField;
    private EditTextBoldCursor portField;
    private EditTextBoldCursor descField;
    private EditTextBoldCursor rsaField;
    private EditTextBoldCursor mainDcField;
    private View mainDcRow;
    private View multiDcToggle;
    private boolean multiDcEnabled = false;

    private static final int DEFAULT_PORT = 2398;
    private static final int DEFAULT_SINGLE_MAIN_DC = 2;

    public AddServerFragment(PolySrvServer existing, OnSavedListener listener) {
        this.editingServer    = existing;
        this.onSavedListener  = listener;
    }

    @Override
    public View createView(Context context) {
        boolean isEdit = (editingServer != null);
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setTitle(isEdit ? "Edit Server" : "New Server");
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override
            public void onItemClick(int id) {
                if (id == -1) finishFragment();
                else if (id == 1) save();
            }
        });
        actionBar.createMenu().addItem(1, "Save");

        ScrollView scroll = new ScrollView(context);
        scroll.setFillViewport(true);

        LinearLayout content = new LinearLayout(context);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(0, dp(8), 0, dp(16));
        content.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray));
        scroll.addView(content, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        // Section: name + description
        content.addView(buildSectionHeader(context, "General"));
        LinearLayout section1 = buildCard(context);
        nameField = buildField(context, "Name", InputType.TYPE_CLASS_TEXT, EditorInfo.IME_ACTION_NEXT);
        addFieldToCard(section1, nameField, true);
        descField = buildField(context, "Description (optional)", InputType.TYPE_CLASS_TEXT, EditorInfo.IME_ACTION_NEXT);
        addFieldToCard(section1, descField, false);
        content.addView(section1);

        // Section: connection
        content.addView(buildSectionHeader(context, "Connection"));
        LinearLayout section2 = buildCard(context);
        hostField = buildField(context, "Host / IP address", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI, EditorInfo.IME_ACTION_NEXT);
        addFieldToCard(section2, hostField, true);
        portField = buildField(context, "Port", InputType.TYPE_CLASS_NUMBER, EditorInfo.IME_ACTION_NEXT);
        portField.setText(String.valueOf(DEFAULT_PORT));
        addFieldToCard(section2, portField, false);
        content.addView(section2);

        // Section: advanced
        content.addView(buildSectionHeader(context, "Advanced"));
        LinearLayout section3 = buildCard(context);
        multiDcToggle = buildToggleRow(context, "Multi-DC mode",
                "Only for Telegram-compatible servers", false);
        section3.addView(multiDcToggle);

        // Main DC selector — single-server only. Hidden when Multi-DC is on
        // (Telegram-compatible servers always use DC 2 as home).
        LinearLayout mainDcContainer = new LinearLayout(context);
        mainDcContainer.setOrientation(LinearLayout.VERTICAL);
        addDividerToCard(mainDcContainer, context);
        mainDcField = buildField(context, "Main data center (1-5)", InputType.TYPE_CLASS_NUMBER, EditorInfo.IME_ACTION_NEXT);
        mainDcField.setText(String.valueOf(DEFAULT_SINGLE_MAIN_DC));
        addFieldToCard(mainDcContainer, mainDcField, true);
        section3.addView(mainDcContainer);
        mainDcRow = mainDcContainer;

        addDividerToCard(section3, context);
        rsaField = buildField(context, "RSA Public Key (PEM)", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_LONG_MESSAGE, EditorInfo.IME_ACTION_DONE);
        rsaField.setMinLines(3);
        rsaField.setGravity(Gravity.TOP);
        addFieldToCard(section3, rsaField, true);
        content.addView(section3);
        updateMainDcVisibility();

        // Save button
        content.addView(buildSaveButton(context));

        // Pre-fill if editing
        if (isEdit) {
            nameField.setText(editingServer.name);
            descField.setText(editingServer.description);
            hostField.setText(editingServer.host);
            portField.setText(String.valueOf(editingServer.port));
            rsaField.setText(editingServer.rsaPublicKey);
            mainDcField.setText(String.valueOf(editingServer.mainDcId > 0
                    ? editingServer.mainDcId : DEFAULT_SINGLE_MAIN_DC));
            multiDcEnabled = editingServer.multiDc;
            updateToggleState();
            updateMainDcVisibility();
        }

        fragmentView = new FrameLayout(context);
        ((FrameLayout) fragmentView).addView(scroll, LayoutHelper.createFrame(
                LayoutHelper.MATCH_PARENT, LayoutHelper.MATCH_PARENT));
        return fragmentView;
    }

    // --- Save logic ---

    private void save() {
        String name = nameField.getText().toString().trim();
        String host = hostField.getText().toString().trim();
        String portStr = portField.getText().toString().trim();

        if (name.isEmpty()) {
            showFieldError(nameField, "Enter a name");
            return;
        }
        if (host.isEmpty()) {
            showFieldError(hostField, "Enter host or IP");
            return;
        }
        int port;
        try {
            port = Integer.parseInt(portStr);
            if (port < 1 || port > 65535) throw new NumberFormatException();
        } catch (NumberFormatException e) {
            showFieldError(portField, "Invalid port (1-65535)");
            return;
        }

        PolySrvServer server;
        if (editingServer != null) {
            server = editingServer;
        } else {
            server = new PolySrvServer();
        }
        int mainDc;
        if (multiDcEnabled) {
            mainDc = 2; // Telegram-compatible servers always home on DC 2
        } else {
            try {
                mainDc = Integer.parseInt(mainDcField.getText().toString().trim());
            } catch (NumberFormatException e) {
                mainDc = DEFAULT_SINGLE_MAIN_DC;
            }
            if (mainDc < 1 || mainDc > 5) mainDc = DEFAULT_SINGLE_MAIN_DC;
        }

        server.name        = name;
        server.host        = host;
        server.port        = port;
        server.description = descField.getText().toString().trim();
        server.rsaPublicKey = rsaField.getText().toString().trim();
        server.multiDc     = multiDcEnabled;
        server.mainDcId    = mainDc;

        if (editingServer != null) {
            PolySrvServers.updateCustomServer(server);
        } else {
            PolySrvServers.addCustomServer(server);
        }

        if (onSavedListener != null) onSavedListener.onSaved(server);
        finishFragment();
    }

    // --- UI helpers ---

    private TextView buildSectionHeader(Context context, String title) {
        TextView tv = new TextView(context);
        tv.setText(title);
        tv.setTextSize(12);
        tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader));
        tv.setPadding(dp(16), dp(12), dp(16), dp(4));
        tv.setAllCaps(true);
        tv.setLetterSpacing(0.06f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        tv.setLayoutParams(lp);
        return tv;
    }

    private LinearLayout buildCard(Context context) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        card.setLayoutParams(lp);
        return card;
    }

    private EditTextBoldCursor buildField(Context context, String hint, int inputType, int imeAction) {
        EditTextBoldCursor et = new EditTextBoldCursor(context);
        et.setHint(hint);
        et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText));
        et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
        et.setTextSize(16);
        et.setInputType(inputType);
        et.setImeOptions(imeAction);
        et.setSingleLine(imeAction != EditorInfo.IME_ACTION_DONE);
        et.setBackground(null);
        et.setPadding(0, dp(8), 0, dp(8));
        return et;
    }

    private void addFieldToCard(LinearLayout card, EditTextBoldCursor field, boolean isFirst) {
        if (!isFirst) addDividerToCard(card, field.getContext());
        LinearLayout wrapper = new LinearLayout(field.getContext());
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(dp(16), dp(4), dp(16), dp(4));
        wrapper.addView(field, LayoutHelper.createLinear(LayoutHelper.MATCH_PARENT, LayoutHelper.WRAP_CONTENT));
        card.addView(wrapper);
    }

    private void addDividerToCard(LinearLayout card, Context context) {
        View divider = new View(context);
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 1);
        lp.setMarginStart(dp(16));
        divider.setLayoutParams(lp);
        card.addView(divider);
    }

    private View buildToggleRow(Context context, String title, String subtitle, boolean checked) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(10), dp(16), dp(10));

        LinearLayout textPart = new LinearLayout(context);
        textPart.setOrientation(LinearLayout.VERTICAL);

        TextView titleTv = new TextView(context);
        titleTv.setText(title);
        titleTv.setTextSize(15);
        titleTv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
        textPart.addView(titleTv);

        TextView subTv = new TextView(context);
        subTv.setText(subtitle);
        subTv.setTextSize(12);
        subTv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText));
        textPart.addView(subTv);

        row.addView(textPart, LayoutHelper.createLinear(0, LayoutHelper.WRAP_CONTENT, 1f));

        // Simple toggle indicator (we manage state manually)
        TextView toggleTv = new TextView(context);
        toggleTv.setTag("toggle");
        toggleTv.setTextSize(13);
        updateToggleText(toggleTv, multiDcEnabled);
        row.addView(toggleTv);

        row.setOnClickListener(v -> {
            multiDcEnabled = !multiDcEnabled;
            updateToggleText(toggleTv, multiDcEnabled);
            updateMainDcVisibility();
        });
        return row;
    }

    private void updateMainDcVisibility() {
        if (mainDcRow != null) {
            mainDcRow.setVisibility(multiDcEnabled ? View.GONE : View.VISIBLE);
        }
    }

    private void updateToggleText(TextView tv, boolean on) {
        tv.setText(on ? "On" : "Off");
        tv.setTextColor(on
                ? Theme.getColor(Theme.key_switch2TrackChecked)
                : Theme.getColor(Theme.key_windowBackgroundWhiteGrayText));
    }

    private void updateToggleState() {
        if (multiDcToggle != null) {
            TextView tv = multiDcToggle.findViewWithTag("toggle");
            if (tv != null) updateToggleText(tv, multiDcEnabled);
        }
    }

    private View buildSaveButton(Context context) {
        TextView btn = new TextView(context);
        btn.setText("Save Server");
        btn.setTextSize(16);
        btn.setTextColor(Color.WHITE);
        btn.setGravity(Gravity.CENTER);
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                dp(10),
                Theme.getColor(Theme.key_featuredStickers_addButton),
                Theme.getColor(Theme.key_featuredStickers_addButtonPressed)));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(52));
        lp.setMargins(dp(16), dp(12), dp(16), dp(8));
        btn.setLayoutParams(lp);
        btn.setOnClickListener(v -> save());
        return btn;
    }

    private void showFieldError(EditTextBoldCursor field, String msg) {
        field.setError(msg);
        field.requestFocus();
        AndroidUtilities.showKeyboard(field);
    }
}
